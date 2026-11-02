import json
import logging
import re

from pydantic import ValidationError

from app.schemas.mind_map import GenerateMapResponse, MindMapEdge, MindMapNode

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


def _resolve_root_node(nodes: list[MindMapNode]) -> MindMapNode:
    """Identify the primary root node of the mind map."""
    for node in nodes:
        if node.data.category and node.data.category.lower() == "root":
            return node
    for node in nodes:
        if node.type == "input":
            return node
    return nodes[0]


def _ensure_graph_connectivity(response_model: GenerateMapResponse) -> None:
    """Connect any valid but disconnected nodes (or subgraphs) to the root node."""
    if len(response_model.nodes) <= 1:
        return

    root_node = _resolve_root_node(response_model.nodes)
    adjacency: dict[str, set[str]] = {node.id: set() for node in response_model.nodes}
    incoming_count: dict[str, int] = {node.id: 0 for node in response_model.nodes}
    existing_edge_ids: set[str] = {edge.id for edge in response_model.edges}

    for edge in response_model.edges:
        adjacency[edge.source].add(edge.target)
        adjacency[edge.target].add(edge.source)
        incoming_count[edge.target] = incoming_count.get(edge.target, 0) + 1

    visited: set[str] = {root_node.id}
    queue: list[str] = [root_node.id]
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency.get(current, ()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    for node in response_model.nodes:
        if node.id in visited:
            continue
        # Prefer attaching the head of an unvisited component (node with no incoming edges)
        if incoming_count.get(node.id, 0) == 0 or node.id not in visited:
            candidate_edge_id = f"edge-auto-{root_node.id}-{node.id}"
            suffix = 1
            while candidate_edge_id in existing_edge_ids:
                suffix += 1
                candidate_edge_id = f"edge-auto-{root_node.id}-{node.id}-{suffix}"
            existing_edge_ids.add(candidate_edge_id)

            response_model.edges.append(
                MindMapEdge(
                    id=candidate_edge_id,
                    source=root_node.id,
                    target=node.id,
                    label=None,
                    animated=False,
                )
            )
            adjacency[root_node.id].add(node.id)
            adjacency[node.id].add(root_node.id)

            comp_queue = [node.id]
            visited.add(node.id)
            while comp_queue:
                curr = comp_queue.pop(0)
                for neigh in adjacency.get(curr, ()):
                    if neigh not in visited:
                        visited.add(neigh)
                        comp_queue.append(neigh)


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

    edge_ids: set[str] = set()
    for edge in response_model.edges:
        if edge.id in edge_ids:
            raise LLMOutputValidationError(
                f"Structural hallucination detected: duplicate edge id '{edge.id}'."
            )
        edge_ids.add(edge.id)
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

    _ensure_graph_connectivity(response_model)
    return response_model
