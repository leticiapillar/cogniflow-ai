from httpx import AsyncClient
from pydantic import ValidationError
import pytest

from app.schemas.mind_map import (
    RELATION_LABELS,
    MindMapEdge,
    MindMapGraph,
    MindMapNode,
    MindMapNodeData,
)


def test_mind_map_graph_contract() -> None:
    """The graph keeps the React Flow node/edge shape and adds pedagogical fields."""
    graph = MindMapGraph(
        topic="Fotossíntese",
        nodes=[
            MindMapNode(
                id="node-root",
                type="input",
                data=MindMapNodeData(label="Fotossíntese", category="root"),
            ),
            MindMapNode(
                id="node-topic-1",
                data=MindMapNodeData(
                    label="Etapas do processo", category="topic", order=1, source_chunks=[2]
                ),
            ),
        ],
        edges=[
            MindMapEdge(
                id="edge-1",
                source="node-root",
                target="node-topic-1",
                relation="has_part",
                label=RELATION_LABELS["has_part"],
            )
        ],
    )
    dumped = graph.model_dump(mode="json")
    assert dumped["nodes"][0]["position"] == {"x": 0.0, "y": 0.0}
    assert dumped["nodes"][1]["data"]["order"] == 1
    assert dumped["edges"][0]["label"] == "inclui"
    assert dumped["edges"][0]["animated"] is False


def test_contract_rejects_unknown_categories_and_relations() -> None:
    with pytest.raises(ValidationError):
        MindMapNodeData(label="X", category="milestone")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        MindMapEdge(id="e", source="a", target="b", relation="relates_to", label="x")  # type: ignore[arg-type]


def test_every_relation_has_one_fixed_verb() -> None:
    assert set(RELATION_LABELS) == {
        "has_part", "is_a", "causes", "depends_on", "precedes", "contrasts", "exemplified_by",
    }
    assert len(set(RELATION_LABELS.values())) == len(RELATION_LABELS)


@pytest.mark.asyncio
async def test_generate_map_endpoint_is_retired(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/generate-map", json={"query": "Fotossíntese"})
    assert response.status_code == 410
    assert "/mind-map" in response.json()["detail"]
