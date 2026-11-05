from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal, initialize_database
from app.core.logging import configure_logging
from app.repositories.document_repository import DocumentRepository
from app.routers import document_router, health_router, mind_map_router
from app.services.embeddings import get_embedding_provider
from app.services.llm_provider import get_llm_provider
from app.services.ollama_readiness import check_ollama_readiness
from app.use_cases.mind_map_generation import MindMapGenerationUseCase


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle handler."""
    logger = configure_logging()
    logger.info("Starting up %s...", app.title)
    try:
        await initialize_database()
        async with AsyncSessionLocal() as session:
            schema_issues = await DocumentRepository(session).check_schema(
                get_settings().embedding_dimension
            )
        for issue in schema_issues:
            logger.error("Database schema problem: %s", issue)
        if not schema_issues:
            interrupted = await MindMapGenerationUseCase(
                session_factory=AsyncSessionLocal,
                llm_provider=get_llm_provider(),
                embedding_provider=get_embedding_provider(),
            ).mark_interrupted()
            if interrupted:
                logger.warning("Marked %d interrupted mind map generations as failed.", interrupted)
    except Exception as exc:
        logger.warning("Database auto-initialization skipped on startup: %s", exc)

    # Startup is not blocked: Ollama may still be pulling models (ollama_init).
    # GET /api/health keeps reporting 'degraded' until it is ready.
    readiness = await check_ollama_readiness(get_settings())
    if readiness.ready:
        logger.info(
            "Ollama is ready (embedding dimension=%s).", readiness.embedding_dimension
        )
    else:
        for issue in readiness.issues:
            logger.warning("Ollama not ready: %s", issue)
    yield
    logger.info("Shutting down %s...", app.title)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    configure_logging()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Orchestrator backend for translating dense academic texts into visual mind maps.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def monitor_end_to_end_latency(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Measure end-to-end request processing time and expose X-Process-Time-Ms header."""
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.3f}"
        return response

    application.include_router(health_router)
    application.include_router(document_router)
    application.include_router(mind_map_router)

    return application


app = create_application()
