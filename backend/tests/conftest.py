from collections.abc import AsyncGenerator, Generator

from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.community.postgres import PostgresContainer

from app.core.database import get_db_session, initialize_database
from app.main import app
from app.routers.dependencies import provide_embedding_provider, provide_llm_provider
from app.services.llm_provider import ContextGroundedLocalLLMProvider
from tests.fakes.embeddings import FakeEmbeddingProvider


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Spin up a PostgreSQL + pgvector container for integration tests."""
    container = PostgresContainer("pgvector/pgvector:pg16")
    with container as postgres:
        yield postgres


@pytest_asyncio.fixture
async def db_engine(
    postgres_container: PostgresContainer,
) -> AsyncGenerator[AsyncEngine, None]:
    """Create an async SQLAlchemy engine connected to the Testcontainer instance."""
    sync_url = postgres_container.get_connection_url()
    async_url = sync_url.replace("psycopg2", "asyncpg").replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    engine = create_async_engine(async_url, echo=False)
    await initialize_database(target_engine=engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an isolated async database session for a test function."""
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient with the database session dependency overridden."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    # Never reach a real Ollama server from API tests.
    app.dependency_overrides[provide_embedding_provider] = FakeEmbeddingProvider
    # Temporary: the heuristic provider is removed in plan 03, Etapa 3 (FakeLLMProvider).
    app.dependency_overrides[provide_llm_provider] = ContextGroundedLocalLLMProvider
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
