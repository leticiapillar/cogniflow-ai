from pathlib import Path

from httpx import AsyncClient
import pytest

from app.core.config import Settings
from app.main import app
from app.routers.dependencies import provide_embedding_provider, provide_llm_provider
from app.schemas.mind_map import MindMapGraph, MindMapStatusResponse
from app.services.evaluation_metrics import (
    calculate_entity_recall,
    evaluate_render_success_rate,
)
from app.services.security_audit import audit_environment_isolation
from scripts.demo_pitch import run_live_pitch_demo
from tests.fakes.embeddings import FakeEmbeddingProvider
from tests.fakes.llm import FakeLLMProvider
from tests.fixtures.academic_materials import (
    TWENTY_ACADEMIC_MATERIALS,
    AcademicMaterialSample,
    build_valid_pdf_bytes,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PDF_PATH = PROJECT_ROOT / "Proposta_Projeto_CogniFlow_AI.pdf"


def test_twenty_academic_dataset_completeness() -> None:
    """Ensure the homologation suite contains at least 20 distinct academic materials."""
    assert len(TWENTY_ACADEMIC_MATERIALS) == 20
    filenames = {sample.filename for sample in TWENTY_ACADEMIC_MATERIALS}
    assert len(filenames) == 20


def test_render_success_rate_metric_calculation() -> None:
    """Render Success Rate counts only graphs that parse and respect the tree rules."""
    root = {"id": "node-root", "type": "input", "data": {"label": "Raiz", "category": "root"}}
    topic = {"id": "t1", "data": {"label": "Eixo", "category": "topic", "order": 1, "source_chunks": [0]}}
    concept = {"id": "k1", "data": {"label": "Conceito", "category": "concept", "source_chunks": [0]}}

    def edge(source: str, target: str) -> dict[str, str]:
        return {"id": f"{source}-{target}", "source": source, "target": target,
                "relation": "has_part", "label": "inclui"}

    valid = MindMapGraph.model_validate(
        {"topic": "Tema", "nodes": [root, topic, concept],
         "edges": [edge("node-root", "t1"), edge("t1", "k1")]}
    ).model_dump_json()
    dangling = MindMapGraph.model_validate(
        {"topic": "Tema", "nodes": [root, topic], "edges": [edge("node-root", "t1"), edge("t1", "missing")]}
    ).model_dump_json()

    rate = evaluate_render_success_rate([valid, valid, "{malformed json", dangling])
    assert rate == 0.5


def test_environment_variable_isolation_and_secret_masking() -> None:
    """Verify institutional API keys and DB credentials are isolated and masked."""
    settings = Settings(
        GEMINI_API_KEY="AIzaSyDummyInstitutionalSecretKey123456",
        POSTGRES_PASSWORD="super_secret_db_password",
        DATABASE_URL="postgresql+asyncpg://user:super_secret_db_password@db:5432/prod",
    )

    violations = audit_environment_isolation(
        project_root=PROJECT_ROOT,
        settings=settings,
    )
    assert violations == []

    assert "AIzaSyDummyInstitutionalSecretKey123456" not in repr(settings)
    assert "super_secret_db_password" not in repr(settings)

    safe_summary = settings.get_safe_config_summary()
    assert safe_summary["gemini_api_key"] == "***REDACTED***"
    assert safe_summary["postgres_password"] == "***REDACTED***"
    assert safe_summary["database_url_override"] == "***REDACTED***"


@pytest.mark.asyncio
async def test_live_pitch_demo_runs_the_map_reduce_pipeline() -> None:
    """The demo wiring (ingest -> map -> reduce) works offline with test doubles."""
    result = await run_live_pitch_demo(
        SAMPLE_PDF_PATH,
        embedding_provider=FakeEmbeddingProvider(),
        llm_provider=FakeLLMProvider(),
    )
    assert result.sections >= 1
    assert result.failed_sections == 0
    assert result.mind_map.nodes[0].data.category == "root"
    assert len(result.mind_map.edges) == len(result.mind_map.nodes) - 1


@pytest.mark.llm
@pytest.mark.asyncio
async def test_live_pitch_demo_with_ollama() -> None:
    """Quality check with the real models (pytest -m llm)."""
    result = await run_live_pitch_demo(SAMPLE_PDF_PATH)
    assert result.failed_sections == 0
    assert result.recall.recall_score >= 0.5


@pytest.mark.llm
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sample",
    TWENTY_ACADEMIC_MATERIALS,
    ids=[item.filename for item in TWENTY_ACADEMIC_MATERIALS],
)
async def test_twenty_academic_materials_end_to_end_evaluation(
    sample: AcademicMaterialSample,
    async_client: AsyncClient,
) -> None:
    """Ingest each material, generate its whole-document map with Ollama, and measure recall."""
    app.dependency_overrides.pop(provide_embedding_provider, None)
    app.dependency_overrides.pop(provide_llm_provider, None)

    files = {"file": (sample.filename, build_valid_pdf_bytes(sample.content), "application/pdf")}
    ingest_response = await async_client.post("/api/documents/ingest", files=files)
    assert ingest_response.status_code == 201
    document_id = ingest_response.json()["document_id"]

    # The background generation finishes before the ASGI test transport returns.
    status = MindMapStatusResponse.model_validate(
        (await async_client.get(f"/api/documents/{document_id}/mind-map")).json()
    )
    assert status.status in ("ready", "partial"), status.error
    assert status.mind_map is not None

    recall = calculate_entity_recall(
        expected_entities=sample.expected_entities,
        mind_map=status.mind_map,
    )
    assert recall.recall_score >= 0.75, (
        f"Recall too low for {sample.filename}: {recall.recall_score} "
        f"(missing: {recall.missing_entities})"
    )
