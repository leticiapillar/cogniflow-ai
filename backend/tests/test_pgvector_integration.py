from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import DocumentRepository
from app.repositories.models import EMBEDDING_DIMENSION


@pytest.mark.asyncio
async def test_health_endpoint_with_pgvector_container(
    async_client: AsyncClient,
) -> None:
    """Verify GET /api/health reports healthy when connected to pgvector container."""
    response = await async_client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database_connected"] is True


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

