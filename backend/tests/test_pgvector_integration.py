from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.main import app
from app.repositories.document_repository import DocumentRepository
from app.repositories.models import EMBEDDING_DIMENSION
from app.routers.health import get_readiness_checker
from app.services.ollama_readiness import OllamaReadiness


@pytest.mark.asyncio
async def test_health_endpoint_with_pgvector_container(
    async_client: AsyncClient,
) -> None:
    """Verify GET /api/health reports healthy when pgvector and (stubbed) Ollama are ready."""

    async def ready_checker(_: Settings) -> OllamaReadiness:
        return OllamaReadiness(reachable=True, embedding_dimension=1024)

    app.dependency_overrides[get_readiness_checker] = lambda: ready_checker
    response = await async_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database_connected"] is True
    assert body["ollama_connected"] is True
    assert body["issues"] == []


@pytest.mark.asyncio
async def test_health_endpoint_degraded_when_ollama_unavailable(
    async_client: AsyncClient,
) -> None:
    """Verify GET /api/health reports degraded with the reason when Ollama is not ready."""

    async def unavailable_checker(_: Settings) -> OllamaReadiness:
        return OllamaReadiness(issues=["Ollama server is unreachable at http://x"])

    app.dependency_overrides[get_readiness_checker] = lambda: unavailable_checker
    response = await async_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database_connected"] is True
    assert body["ollama_connected"] is False
    assert body["issues"] == ["Ollama server is unreachable at http://x"]


@pytest.mark.asyncio
async def test_store_and_similarity_search_with_pgvector(
    db_session: AsyncSession,
) -> None:
    """Verify storing document chunks and performing cosine similarity search in pgvector."""
    repository = DocumentRepository(session=db_session)

    vector_biology = [1.0] + [0.0] * (EMBEDDING_DIMENSION - 1)
    vector_physics = [0.0, 1.0] + [0.0] * (EMBEDDING_DIMENSION - 2)

    await repository.add_chunk(
        document_name="biology_101.pdf",
        chunk_index=0,
        content="Mitochondria are the powerhouse of the cell.",
        embedding=vector_biology,
    )
    await repository.add_chunk(
        document_name="physics_101.pdf",
        chunk_index=0,
        content="Newton's second law states that force equals mass times acceleration.",
        embedding=vector_physics,
    )

    results = await repository.search_similar_chunks(
        query_embedding=vector_biology,
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].document_name == "biology_101.pdf"
    assert "Mitochondria" in results[0].content

