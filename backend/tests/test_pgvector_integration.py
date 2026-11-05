import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.main import app
from app.repositories.document_repository import DocumentRepository
from app.repositories.models import EMBEDDING_DIMENSION, DocumentModel
from app.routers.health import get_readiness_checker
from app.schemas.document import IngestedChunkPayload
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


def unit_vector(position: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[position] = 1.0
    return vector


def chunk_payload(index: int, content: str, embedding: list[float]) -> IngestedChunkPayload:
    return IngestedChunkPayload(
        chunk_index=index,
        content=content,
        section_title="Seção",
        page_start=1,
        page_end=1,
        embedding=embedding,
    )


async def store_document(
    repository: DocumentRepository,
    name: str,
    model: str,
    chunks: list[IngestedChunkPayload],
) -> DocumentModel:
    document, _ = await repository.replace_document(
        name=name,
        sha256="0" * 64,
        page_count=1,
        embedding_model=model,
        embedding_dimension=EMBEDDING_DIMENSION,
        chunks=chunks,
    )
    return document


@pytest.mark.asyncio
async def test_store_and_similarity_search_with_pgvector(
    db_session: AsyncSession,
) -> None:
    """Verify storing documents and performing cosine similarity search in pgvector."""
    repository = DocumentRepository(session=db_session)
    model = f"model-{uuid.uuid4()}"

    biology = await store_document(
        repository,
        f"biology-{uuid.uuid4()}.pdf",
        model,
        [chunk_payload(0, "Mitochondria are the powerhouse of the cell.", unit_vector(0))],
    )
    await store_document(
        repository,
        f"physics-{uuid.uuid4()}.pdf",
        model,
        [chunk_payload(0, "Force equals mass times acceleration.", unit_vector(1))],
    )

    results = await repository.search_similar_chunks(
        query_embedding=unit_vector(0),
        embedding_model=model,
        top_k=1,
    )

    assert len(results) == 1
    assert results[0].document_id == biology.id
    assert "Mitochondria" in results[0].content


@pytest.mark.asyncio
async def test_search_ignores_vectors_from_other_embedding_models(
    db_session: AsyncSession,
) -> None:
    """Vectors from another model are never compared with the query vector."""
    repository = DocumentRepository(session=db_session)
    current_model = f"current-{uuid.uuid4()}"

    await store_document(
        repository,
        f"legacy-{uuid.uuid4()}.pdf",
        f"legacy-{uuid.uuid4()}",
        [chunk_payload(0, "Legacy vector", unit_vector(0))],
    )

    results = await repository.search_similar_chunks(
        query_embedding=unit_vector(0),
        embedding_model=current_model,
        top_k=5,
    )
    assert results == []


@pytest.mark.asyncio
async def test_filtered_search_returns_top_k_with_hnsw_index(
    db_session: AsyncSession,
) -> None:
    """A document filter still yields top_k rows when other documents dominate the index."""
    repository = DocumentRepository(session=db_session)
    model = f"model-{uuid.uuid4()}"

    for _ in range(3):
        await store_document(
            repository,
            f"noise-{uuid.uuid4()}.pdf",
            model,
            [chunk_payload(i, f"noise {i}", unit_vector(0)) for i in range(60)],
        )
    target = await store_document(
        repository,
        f"target-{uuid.uuid4()}.pdf",
        model,
        [chunk_payload(i, f"target {i}", unit_vector(1)) for i in range(8)],
    )

    results = await repository.search_similar_chunks(
        query_embedding=unit_vector(0),
        embedding_model=model,
        top_k=5,
        document_id=target.id,
    )
    assert len(results) == 5
    assert all(chunk.document_id == target.id for chunk in results)


@pytest.mark.asyncio
async def test_replace_document_overwrites_chunks_and_cascades(
    db_session: AsyncSession,
) -> None:
    """Re-ingesting a document replaces its chunks instead of duplicating them."""
    repository = DocumentRepository(session=db_session)
    name = f"lecture-{uuid.uuid4()}.pdf"
    model = f"model-{uuid.uuid4()}"

    first = await store_document(
        repository, name, model, [chunk_payload(i, f"v1 {i}", unit_vector(i)) for i in range(3)]
    )
    second = await store_document(
        repository, name, model, [chunk_payload(0, "v2", unit_vector(0))]
    )

    assert first.id != second.id
    assert await repository.get_chunks_by_document(first.id) == []
    chunks = await repository.get_chunks_by_document(second.id)
    assert [chunk.content for chunk in chunks] == ["v2"]


@pytest.mark.asyncio
async def test_schema_check_and_hnsw_index(db_session: AsyncSession) -> None:
    """The created schema matches the configured dimension and has the HNSW index."""
    repository = DocumentRepository(session=db_session)

    assert await repository.check_schema(EMBEDDING_DIMENSION) == []
    issues = await repository.check_schema(EMBEDDING_DIMENSION + 1)
    assert len(issues) == 1 and "migrate_03.sql" in issues[0]

    result = await db_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'ix_document_chunks_embedding_hnsw'"
        )
    )
    index_definition = result.scalar_one()
    assert "hnsw" in index_definition
    assert "vector_cosine_ops" in index_definition
