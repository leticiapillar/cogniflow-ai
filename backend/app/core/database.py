from collections.abc import AsyncGenerator
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger("cogniflow.database")


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative ORM models."""


def create_db_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    settings = get_settings()
    url = database_url or settings.database_url
    return create_async_engine(url, echo=False, pool_pre_ping=True)


engine: AsyncEngine = create_db_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def initialize_database(target_engine: AsyncEngine | None = None) -> None:
    """Initialize pgvector extension and database schema."""
    active_engine = target_engine or engine
    async with active_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Iterative HNSW scans (used by filtered similarity search) need pgvector >= 0.8.
        await connection.execute(text("ALTER EXTENSION vector UPDATE"))
        await connection.run_sync(Base.metadata.create_all)
    logger.info("Database initialized with pgvector extension enabled.")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """FastAPI dependency for work that outlives the request (background generation)."""
    return AsyncSessionLocal
