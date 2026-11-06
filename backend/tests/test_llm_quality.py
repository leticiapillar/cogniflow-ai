"""Quality gates with the real models (pytest -m llm). Needs Ollama with the configured
LLM and bge-m3. Minimums come from the plan 03 evaluation (docs/avaliacao-modelos.md)
with some slack, since a 3B model is not deterministic across runs."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.embeddings import get_embedding_provider
from app.services.llm_provider import get_llm_provider
from evaluation.datasets import PHOTOSYNTHESIS_PDF, TUTOR_QUESTIONS, map_references
from evaluation.runner import accessibility_of, evaluate_map, evaluate_tutor, ingest_for_tutor

pytestmark = [pytest.mark.llm, pytest.mark.asyncio]


async def test_mind_map_of_the_photosynthesis_class() -> None:
    settings = Settings()
    [reference] = map_references(academic_samples=0)

    result = await evaluate_map(reference, get_llm_provider(settings), get_embedding_provider(settings), settings)

    assert result.status == "ready", result.error
    assert result.structural_errors == []
    assert 3 <= result.topics <= 5
    assert result.recall >= 0.75, result.missing_entities
    assert (result.label_grounding_rate or 0) >= 0.8
    assert accessibility_of(result.texts, result.labels)["adherence"] >= 0.8


async def test_tutor_answers_from_the_material_and_refuses_the_rest(db_engine: AsyncEngine) -> None:
    settings = Settings()
    embedder = get_embedding_provider(settings)
    sessions = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)
    document_id = await ingest_for_tutor(sessions, PHOTOSYNTHESIS_PDF.read_bytes(), embedder, settings)

    results = await evaluate_tutor(
        sessions, document_id, TUTOR_QUESTIONS, get_llm_provider(settings), embedder, settings.tutor_top_k
    )
    threshold = settings.tutor_min_similarity

    assert all(r.error is None for r in results)
    assert sum(r.correct_with(threshold) for r in results if r.in_material) >= 8
    assert sum(r.correct_with(threshold) for r in results if not r.in_material) == 5
    # The threshold must never block an answerable question.
    assert all(r.best_similarity >= threshold for r in results if r.in_material)
