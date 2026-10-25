import json
from pathlib import Path

from httpx import AsyncClient
import pytest

from app.core.config import Settings
from app.schemas.mind_map import GenerateMapResponse
from app.services.evaluation_metrics import (
    calculate_entity_recall,
    evaluate_render_success_rate,
)
from app.services.security_audit import audit_environment_isolation
from scripts.demo_pitch import run_live_pitch_demo
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
    """Verify Render Success Rate accurately distinguishes valid and invalid JSON outputs."""
    valid_json = json.dumps(
        {
            "topic": "Thermodynamics",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {"label": "Entropy", "summary": "Disorder", "category": "root"},
                }
            ],
            "edges": [],
        }
    )
    invalid_json = "{malformed json"
    dangling_edge_json = json.dumps(
        {
            "topic": "Broken Graph",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {"label": "Root", "summary": "Summary", "category": "root"},
                }
            ],
            "edges": [{"id": "e1", "source": "node-root", "target": "missing"}],
        }
    )

    rate = evaluate_render_success_rate([valid_json, valid_json, invalid_json, dangling_edge_json])
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
async def test_live_pitch_prototype_pdf_conversion() -> None:
    """Verify the live pitch demo script converts Proposta_Projeto_CogniFlow_AI.pdf in under 2 minutes."""
    mind_map, recall_result, total_latency_ms = await run_live_pitch_demo(SAMPLE_PDF_PATH)

    assert len(mind_map.nodes) >= 2
    assert len(mind_map.edges) >= 1
    assert recall_result.recall_score >= 0.5
    assert total_latency_ms < 120_000.0


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
    """Iterate over all 20 academic materials, measuring Recall, Render Success, and Latency."""
    pdf_bytes = build_valid_pdf_bytes(sample.content)
    files = {"file": (sample.filename, pdf_bytes, "application/pdf")}

    ingest_response = await async_client.post("/api/documents/ingest", files=files)
    assert ingest_response.status_code == 201
    assert "X-Process-Time-Ms" in ingest_response.headers

    map_response = await async_client.post(
        "/api/generate-map",
        json={
            "query": sample.query,
            "document_name": sample.filename,
            "top_k": 5,
        },
    )
    assert map_response.status_code == 200
    assert "X-Process-Time-Ms" in map_response.headers
    header_latency_ms = float(map_response.headers["X-Process-Time-Ms"])

    validated_map = GenerateMapResponse.model_validate(map_response.json())
    assert validated_map.source_chunks_used >= 1
    assert validated_map.generation_latency_ms > 0.0
    assert validated_map.generation_latency_ms < 120_000.0
    assert header_latency_ms < 120_000.0

    recall = calculate_entity_recall(
        expected_entities=sample.expected_entities,
        mind_map=validated_map,
    )
    assert recall.recall_score >= 0.75, (
        f"Recall too low for {sample.filename}: {recall.recall_score} "
        f"(missing: {recall.missing_entities})"
    )

