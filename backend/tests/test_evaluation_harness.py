"""Fast checks of the evaluation logic itself (the real-model runs live in `evaluation/`)."""

import json
from typing import Any

from app.services.llm_provider import BaseLLMProvider
from app.services.mind_map.pipeline import MindMapPipeline
from app.services.mind_map.units import MapUnit
from app.schemas.mind_map import MindMapGraph
from app.services.evaluation_metrics import calculate_entity_recall
from evaluation.accessibility import evaluate_texts
from evaluation.datasets import TUTOR_QUESTIONS
from evaluation.instrumentation import RecordingLLMProvider
from evaluation.runner import TutorResult, calibrate_threshold
from tests.fakes.embeddings import FakeEmbeddingProvider
from tests.fakes.llm import ScriptedLLMProvider


def result(in_material: bool, similarity: float, llm_found: bool, ok: bool = True) -> TutorResult:
    return TutorResult("pergunta", in_material, similarity, llm_found, page_ok=ok, keywords_ok=ok, seconds=1.0)


def test_tutor_dataset_has_ten_answerable_and_five_outside_questions() -> None:
    assert sum(q.in_material for q in TUTOR_QUESTIONS) == 10
    assert sum(not q.in_material for q in TUTOR_QUESTIONS) == 5
    assert all(q.pages and q.answer_keywords for q in TUTOR_QUESTIONS if q.in_material)


def test_a_threshold_blocks_answers_and_the_llm_can_still_refuse() -> None:
    answerable = result(True, 0.70, llm_found=True)
    outside_but_close = result(False, 0.60, llm_found=False)

    assert answerable.correct_with(0.65) and not answerable.correct_with(0.75)
    assert outside_but_close.correct_with(-1.0)  # refused by the model itself
    assert not result(True, 0.70, llm_found=True, ok=False).correct_with(0.0)  # wrong page or content


def test_calibration_keeps_a_safety_margin_below_the_answerable_questions() -> None:
    results = [
        result(True, 0.72, True), result(True, 0.64, True), result(True, 0.62, True),
        result(False, 0.57, False),  # same subject: only the model can refuse it
        result(False, 0.41, True), result(False, 0.30, True),  # the model failed to refuse them
    ]

    threshold, correct = calibrate_threshold(results)

    assert threshold == 0.47  # 0.62 - 0.15
    assert correct == 6  # the threshold blocks the off-topic ones, the model refuses the other
    assert all(r.found_with(threshold) for r in results if r.in_material)


class Fixed(BaseLLMProvider):
    model_name = "fixed"

    def __init__(self, answers: list[str]) -> None:
        self.inner = ScriptedLLMProvider(answers)

    async def generate_json(self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]) -> str:
        return await self.inner.generate_json(system_prompt, user_prompt, json_schema)


async def test_recording_groups_corrections_with_their_request() -> None:
    valid = json.dumps({"concepts": [{"label": "Clorofila", "summary": "Pigmento verde.", "source_chunks": [0]}]})
    llm = RecordingLLMProvider(Fixed(["not json", valid, valid]))
    pipeline = MindMapPipeline(llm=llm, embedder=FakeEmbeddingProvider())
    unit = MapUnit(index=0, chunks=[(0, "A clorofila é um pigmento verde.")])

    await pipeline.extract_unit(unit)  # needs one correction
    await pipeline.extract_unit(unit)  # valid at once

    assert [len(request) for request in llm.requests("map_section")] == [2, 1]
    assert llm.first_attempt_rate() == 0.5
    assert [call.is_correction for call in llm.calls] == [False, True, False]


def test_accessibility_heuristics() -> None:
    long_sentence = " ".join(["palavra"] * 21) + "."
    report = evaluate_texts(
        [
            "A clorofila absorve a luz. Ela é verde.",
            long_sentence,
            "O cloroplasto é a fábrica da célula.",
            "Você sabia que a planta respira?",
        ],
        labels=["Clorofila", "Um rótulo longo demais para um mapa mental"],
    )

    assert report.sentences == 5
    assert report.short_sentence_rate == 4 / 5
    assert report.figurative_expressions == 1
    assert report.rhetorical_questions == 1
    assert report.label_rate == 0.5
    assert report.adherence == 1 / 4


def test_entity_recall_ignores_plural_and_accents() -> None:
    """Found in the real-model runs: 'Cloroplasto' did not count for 'Cloroplastos'."""
    graph = MindMapGraph.model_validate({"topic": "Fotossíntese", "nodes": [
        {"id": "r", "type": "input", "data": {"label": "Fotossíntese", "category": "root"}},
        {"id": "a", "data": {"label": "Cloroplasto", "category": "concept", "source_chunks": [0]}},
        {"id": "b", "data": {"label": "Gas carbonico", "category": "concept", "source_chunks": [0]}},
    ], "edges": []})

    recall = calculate_entity_recall(["Cloroplastos", "Gás carbônico", "Pigmento"], graph)

    assert recall.matched_entities == ("Cloroplastos", "Gás carbônico")
    assert recall.missing_entities == ("Pigmento",)
