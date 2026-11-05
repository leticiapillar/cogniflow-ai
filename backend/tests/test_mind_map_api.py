from pathlib import Path
import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.main import app
from app.repositories.models import MindMapModel
from app.routers.dependencies import provide_llm_provider
from app.schemas.mind_map import MindMapStatusResponse
from app.services.mind_map.validation import validate_mind_map_graph
from app.use_cases.mind_map_generation import INTERRUPTED_ERROR, MindMapGenerationUseCase
from tests.fakes.embeddings import FakeEmbeddingProvider
from tests.fakes.llm import (
    FakeLLMProvider,
    SelectiveFailureLLMProvider,
    UnavailableLLMProvider,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHOTOSYNTHESIS_PDF = PROJECT_ROOT / "fotossintese-texto-selecionavel.pdf"


def use_llm(provider: FakeLLMProvider) -> None:
    app.dependency_overrides[provide_llm_provider] = lambda: provider


async def ingest(client: AsyncClient, name: str) -> str:
    files = {"file": (name, PHOTOSYNTHESIS_PDF.read_bytes(), "application/pdf")}
    response = await client.post("/api/documents/ingest", files=files)
    assert response.status_code == 201, response.text
    return response.json()["document_id"]


async def get_status(client: AsyncClient, document_id: str) -> MindMapStatusResponse:
    response = await client.get(f"/api/documents/{document_id}/mind-map")
    assert response.status_code == 200, response.text
    return MindMapStatusResponse.model_validate(response.json())


async def chunk_indices(client: AsyncClient, name: str) -> set[int]:
    chunks = (await client.get(f"/api/documents/{name}/chunks")).json()
    return {chunk["chunk_index"] for chunk in chunks}


def unique_name() -> str:
    return f"fotossintese-{uuid.uuid4().hex[:8]}.pdf"


async def test_ingestion_generates_a_whole_document_map_in_background(
    async_client: AsyncClient,
) -> None:
    llm = FakeLLMProvider()
    use_llm(llm)
    name = unique_name()
    document_id = await ingest(async_client, name)

    status = await get_status(async_client, document_id)
    assert status.status == "ready", status.error
    assert status.progress.phase == "done"
    assert status.progress.total >= 1
    assert status.progress.done == status.progress.total
    assert status.progress.message == "Mapa pronto."
    assert status.failed_sections == []
    assert status.llm_model == "fake-llm"

    graph = status.mind_map
    assert graph is not None
    assert validate_mind_map_graph(graph, await chunk_indices(async_client, name)) == []
    topics = [n for n in graph.nodes if n.data.category == "topic"]
    assert 3 <= len(topics) <= 5
    assert sorted(t.data.order for t in topics) == list(range(1, len(topics) + 1))

    extraction_calls = [prompt for task, prompt in llm.calls if task == "extraction"]
    assert len(extraction_calls) == status.progress.total
    assert any("[Trecho 0]" in prompt for prompt in extraction_calls)


async def test_unchanged_pdf_reuses_document_and_map(async_client: AsyncClient) -> None:
    use_llm(FakeLLMProvider())
    name = unique_name()
    document_id = await ingest(async_client, name)
    first = await get_status(async_client, document_id)

    second_llm = FakeLLMProvider()
    use_llm(second_llm)
    assert await ingest(async_client, name) == document_id

    second = await get_status(async_client, document_id)
    assert second.updated_at == first.updated_at
    assert second_llm.calls == []


async def test_regenerate_rebuilds_the_map(async_client: AsyncClient) -> None:
    use_llm(FakeLLMProvider())
    document_id = await ingest(async_client, unique_name())

    other = FakeLLMProvider(model_name="other-llm")
    use_llm(other)
    response = await async_client.post(f"/api/documents/{document_id}/mind-map/regenerate")
    assert response.status_code == 202

    status = await get_status(async_client, document_id)
    assert status.status == "ready"
    assert status.llm_model == "other-llm"
    assert other.calls


async def test_regenerate_is_refused_while_a_generation_runs(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    use_llm(FakeLLMProvider())
    document_id = await ingest(async_client, unique_name())
    await db_session.execute(
        update(MindMapModel)
        .where(MindMapModel.document_id == uuid.UUID(document_id))
        .values(status="processing", phase="mapping")
    )
    await db_session.commit()

    response = await async_client.post(f"/api/documents/{document_id}/mind-map/regenerate")
    assert response.status_code == 409


async def test_failed_section_yields_partial_map_and_can_be_retried(
    async_client: AsyncClient,
) -> None:
    use_llm(SelectiveFailureLLMProvider(lambda task, prompt: task == "extraction" and "[Trecho 0]" in prompt))
    document_id = await ingest(async_client, unique_name())

    status = await get_status(async_client, document_id)
    assert status.status == "partial", status.error
    assert status.mind_map is not None
    assert len(status.failed_sections) == 1
    failed = status.failed_sections[0]
    assert failed.section_index == 0
    assert "after 3 attempts" in failed.reason
    assert status.progress.message == "Mapa pronto. Algumas seções não puderam ser processadas."

    not_failed = await async_client.post(f"/api/documents/{document_id}/mind-map/sections/1/retry")
    assert not_failed.status_code == 409

    use_llm(FakeLLMProvider())
    retry = await async_client.post(f"/api/documents/{document_id}/mind-map/sections/0/retry")
    assert retry.status_code == 202

    status = await get_status(async_client, document_id)
    assert status.status == "ready"
    assert status.failed_sections == []


async def test_map_fails_explicitly_when_the_llm_is_unavailable(async_client: AsyncClient) -> None:
    use_llm(UnavailableLLMProvider())
    document_id = await ingest(async_client, unique_name())

    status = await get_status(async_client, document_id)
    assert status.status == "failed"
    assert status.mind_map is None
    assert status.error == "No section of the material could be processed."
    assert len(status.failed_sections) == status.progress.total
    assert all("unavailable" in section.reason for section in status.failed_sections)
    assert status.progress.message == "Não foi possível gerar o mapa."


async def test_map_fails_when_the_organization_step_keeps_failing(async_client: AsyncClient) -> None:
    use_llm(SelectiveFailureLLMProvider(lambda task, prompt: task == "organization"))
    document_id = await ingest(async_client, unique_name())

    status = await get_status(async_client, document_id)
    assert status.status == "failed"
    assert "MapOrganization after 3 attempts" in (status.error or "")


async def test_unknown_document_and_retired_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get(f"/api/documents/{uuid.uuid4()}/mind-map")
    assert response.status_code == 404
    response = await async_client.post(f"/api/documents/{uuid.uuid4()}/mind-map/regenerate")
    assert response.status_code == 404


async def test_startup_marks_interrupted_generations_as_failed(
    async_client: AsyncClient, db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    use_llm(FakeLLMProvider())
    document_id = await ingest(async_client, unique_name())
    await db_session.execute(
        update(MindMapModel)
        .where(MindMapModel.document_id == uuid.UUID(document_id))
        .values(status="processing", phase="mapping")
    )
    await db_session.commit()

    use_case = MindMapGenerationUseCase(
        session_factory=async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False),
        llm_provider=FakeLLMProvider(),
        embedding_provider=FakeEmbeddingProvider(),
    )
    assert await use_case.mark_interrupted() >= 1

    status = await get_status(async_client, document_id)
    assert status.status == "failed"
    assert status.error == INTERRUPTED_ERROR
