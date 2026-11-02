import json
import logging
import re

from pydantic import ValidationError

from app.schemas.mind_map import GenerateMapResponse

logger = logging.getLogger("cogniflow.services.output_validator")

MARKDOWN_JSON_FENCE_REGEX = re.compile(
    r"^\s*```(?:json)?\s*(?P<body>[\s\S]*?)\s*```\s*$", re.IGNORECASE
)


class LLMOutputValidationError(ValueError):
    """Raised when the LLM response violates the JSON schema or structural graph constraints."""


def _clean_json_string(raw_output: str) -> str:
    """Strip optional markdown code fences surrounding a JSON object."""
    text = raw_output.strip()
    fence_match = MARKDOWN_JSON_FENCE_REGEX.match(text)
    if fence_match:
        return fence_match.group("body").strip()
    return text


def _replace_root_label(parsed_dict: dict[str, object], expected_topic: str) -> None:
    """Use the trusted user query as the visual label of the root node."""
    nodes = parsed_dict.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return

    root_node: dict[str, object] | None = None
    for candidate in nodes:
        if not isinstance(candidate, dict):
            continue
        data = candidate.get("data")
        category = data.get("category") if isinstance(data, dict) else None
        if isinstance(category, str) and category.lower() == "root":
            root_node = candidate
            break

    if root_node is None:
        root_node = next(
            (
                candidate
                for candidate in nodes
                if isinstance(candidate, dict) and candidate.get("type") == "input"
            ),
            None,
        )

    if root_node is None and isinstance(nodes[0], dict):
        root_node = nodes[0]

    if root_node is not None and isinstance(root_node.get("data"), dict):
        root_node["data"]["label"] = expected_topic[:200]


def validate_and_parse_mind_map_json(
    raw_output: str,
    source_chunks_used: int = 0,
    generation_latency_ms: float = 0.0,
    expected_topic: str | None = None,
) -> GenerateMapResponse:
    """Validate LLM JSON string against Pydantic contracts and graph structural rules."""
    if not raw_output or not raw_output.strip():
        raise LLMOutputValidationError("LLM returned an empty response.")

    cleaned_json = _clean_json_string(raw_output)
    try:
        parsed_dict = json.loads(cleaned_json)
    except json.JSONDecodeError as exc:
        logger.error("LLM output is not valid JSON: %s", exc)
        raise LLMOutputValidationError(
            f"LLM output is not valid JSON: {exc}"
        ) from exc

    if not isinstance(parsed_dict, dict):
        raise LLMOutputValidationError("LLM JSON root must be an object.")

    if expected_topic is not None:
        parsed_dict["topic"] = expected_topic
        _replace_root_label(parsed_dict, expected_topic)
    parsed_dict["source_chunks_used"] = source_chunks_used
    parsed_dict["generation_latency_ms"] = round(max(0.0, generation_latency_ms), 3)

    try:
        response_model = GenerateMapResponse.model_validate(parsed_dict)
    except ValidationError as exc:
        logger.error("LLM output failed Pydantic schema validation: %s", exc)
        raise LLMOutputValidationError(
            f"LLM output violated GenerateMapResponse contract: {exc}"
        ) from exc

    node_ids: set[str] = set()
    for node in response_model.nodes:
        if node.id in node_ids:
            raise LLMOutputValidationError(
                f"Structural hallucination detected: duplicate node id '{node.id}'."
            )
        node_ids.add(node.id)

    for edge in response_model.edges:
        if edge.source not in node_ids:
            raise LLMOutputValidationError(
                f"Structural hallucination detected: edge '{edge.id}' references nonexistent source node '{edge.source}'."
            )
        if edge.target not in node_ids:
            raise LLMOutputValidationError(
                f"Structural hallucination detected: edge '{edge.id}' references nonexistent target node '{edge.target}'."
            )
        if edge.source == edge.target:
            raise LLMOutputValidationError(
                f"Structural hallucination detected: edge '{edge.id}' forms a self-loop on node '{edge.source}'."
            )

    return response_model
