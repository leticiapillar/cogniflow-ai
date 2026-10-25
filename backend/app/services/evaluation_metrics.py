from dataclasses import dataclass
import re
from typing import Sequence

from app.schemas.mind_map import GenerateMapResponse
from app.services.output_validator import (
    LLMOutputValidationError,
    validate_and_parse_mind_map_json,
)


@dataclass(frozen=True)
class RecallEvaluationResult:
    """Result of cross-referencing PDF academic entities against generated mind map nodes."""

    expected_entities: tuple[str, ...]
    matched_entities: tuple[str, ...]
    missing_entities: tuple[str, ...]
    recall_score: float


@dataclass(frozen=True)
class BenchmarkSummaryReport:
    """Aggregated homologation metrics across the 20 academic material evaluations."""

    total_samples: int
    successful_renders: int
    render_success_rate: float
    mean_recall_score: float
    mean_latency_ms: float
    max_latency_ms: float


def extract_reference_entities(academic_text: str) -> list[str]:
    """Extract reference academic entities defined as 'Concept: explanation' in source text."""
    entities: list[str] = []
    seen: set[str] = set()
    for raw_line in academic_text.splitlines():
        line = raw_line.strip(" #\t●*-")
        if ":" in line:
            candidate = line.split(":", 1)[0].strip()
            normalized = candidate.lower()
            if 1 <= len(candidate.split()) <= 6 and normalized not in seen:
                seen.add(normalized)
                entities.append(candidate)
    return entities


def calculate_entity_recall(
    expected_entities: Sequence[str],
    mind_map: GenerateMapResponse,
) -> RecallEvaluationResult:
    """Compute entity coverage (Recall) by crossing PDF entities with generated JSON nodes."""
    cleaned_expected = [e.strip() for e in expected_entities if e and e.strip()]
    if not cleaned_expected:
        return RecallEvaluationResult(
            expected_entities=(),
            matched_entities=(),
            missing_entities=(),
            recall_score=1.0,
        )

    combined_nodes_text = " ".join(
        f"{node.data.label} {node.data.summary or ''}" for node in mind_map.nodes
    ).lower()
    normalized_corpus = re.sub(r"\s+", " ", combined_nodes_text)

    matched: list[str] = []
    missing: list[str] = []

    for entity in cleaned_expected:
        entity_lower = entity.lower()
        if entity_lower in normalized_corpus:
            matched.append(entity)
            continue

        significant_tokens = [
            tok for tok in re.findall(r"[a-zA-ZÀ-ÿ0-9]{4,}", entity_lower)
        ]
        if significant_tokens and all(
            tok in normalized_corpus for tok in significant_tokens
        ):
            matched.append(entity)
        else:
            missing.append(entity)

    recall = len(matched) / len(cleaned_expected)
    return RecallEvaluationResult(
        expected_entities=tuple(cleaned_expected),
        matched_entities=tuple(matched),
        missing_entities=tuple(missing),
        recall_score=round(recall, 4),
    )


def evaluate_render_success_rate(raw_json_outputs: Sequence[str]) -> float:
    """Measure static JSON validation success rate across a batch of LLM outputs."""
    if not raw_json_outputs:
        return 0.0

    valid_count = 0
    for raw_output in raw_json_outputs:
        try:
            validate_and_parse_mind_map_json(raw_output)
            valid_count += 1
        except LLMOutputValidationError:
            continue

    return round(valid_count / len(raw_json_outputs), 4)

