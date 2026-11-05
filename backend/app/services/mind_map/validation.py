from collections import Counter, defaultdict

from app.schemas.mind_map import RELATION_LABELS, MindMapGraph

MAX_TOPICS = 5
MAX_CONCEPTS_PER_TOPIC = 5
MAX_EXAMPLES_PER_CONCEPT = 2

ALLOWED_CHILD_CATEGORY = {"root": "topic", "topic": "concept", "concept": "example"}


def validate_mind_map_graph(
    graph: MindMapGraph,
    valid_chunk_indices: set[int] | None = None,
) -> list[str]:
    """Return every violation of the tree structure, cognitive-load limits and citations."""
    errors: list[str] = []
    nodes = {node.id: node for node in graph.nodes}

    for node_id, count in Counter(node.id for node in graph.nodes).items():
        if count > 1:
            errors.append(f"Duplicate node id '{node_id}'.")
    for edge_id, count in Counter(edge.id for edge in graph.edges).items():
        if count > 1:
            errors.append(f"Duplicate edge id '{edge_id}'.")

    roots = [node for node in graph.nodes if node.data.category == "root"]
    if len(roots) != 1:
        errors.append(f"Expected exactly one root node, found {len(roots)}.")

    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        if edge.source not in nodes or edge.target not in nodes:
            errors.append(f"Edge '{edge.id}' references a nonexistent node.")
            continue
        if edge.source == edge.target:
            errors.append(f"Edge '{edge.id}' is a self-loop.")
            continue
        if edge.label != RELATION_LABELS[edge.relation]:
            errors.append(f"Edge '{edge.id}' label does not match relation '{edge.relation}'.")
        parent_category = nodes[edge.source].data.category
        child_category = nodes[edge.target].data.category
        if ALLOWED_CHILD_CATEGORY.get(parent_category) != child_category:
            errors.append(
                f"Edge '{edge.id}' connects '{parent_category}' to '{child_category}'."
            )
        children[edge.source].append(edge.target)
        parents[edge.target].append(edge.source)

    for node in graph.nodes:
        expected_parents = 0 if node.data.category == "root" else 1
        if len(parents[node.id]) != expected_parents:
            errors.append(
                f"Node '{node.id}' has {len(parents[node.id])} parents (expected {expected_parents})."
            )
        if node.data.category != "root" and not node.data.source_chunks:
            errors.append(f"Node '{node.id}' does not cite any source chunk.")
        if valid_chunk_indices is not None:
            unknown = set(node.data.source_chunks) - valid_chunk_indices
            if unknown:
                errors.append(f"Node '{node.id}' cites nonexistent chunks {sorted(unknown)}.")

    if len(roots) == 1:
        reachable = {roots[0].id}
        pending = [roots[0].id]
        while pending:
            for child in children[pending.pop()]:
                if child not in reachable:
                    reachable.add(child)
                    pending.append(child)
        unreachable = set(nodes) - reachable
        if unreachable:
            errors.append(f"Nodes not reachable from the root: {sorted(unreachable)}.")

        topics = children[roots[0].id]
        if not 1 <= len(topics) <= MAX_TOPICS:
            errors.append(f"Expected 1 to {MAX_TOPICS} topics, found {len(topics)}.")
        orders = sorted(nodes[t].data.order or 0 for t in topics if t in nodes)
        if orders != list(range(1, len(topics) + 1)):
            errors.append("Topics must be numbered 1..n in study order.")
        for topic_id in topics:
            concepts = children[topic_id]
            if not 1 <= len(concepts) <= MAX_CONCEPTS_PER_TOPIC:
                errors.append(
                    f"Topic '{topic_id}' has {len(concepts)} concepts "
                    f"(expected 1 to {MAX_CONCEPTS_PER_TOPIC})."
                )
            for concept_id in concepts:
                if len(children[concept_id]) > MAX_EXAMPLES_PER_CONCEPT:
                    errors.append(f"Concept '{concept_id}' has too many examples.")

    return errors
