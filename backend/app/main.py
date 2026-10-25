from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import initialize_database
from app.core.logging import configure_logging
from app.routers import document_router, health_router, mind_map_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle handler."""
    logger = configure_logging()
    logger.info("Starting up %s...", app.title)
    try:
        await initialize_database()
    except Exception as exc:
        logger.warning("Database auto-initialization skipped on startup: %s", exc)
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
