from httpx import AsyncClient
import pytest
from pydantic import ValidationError

from app.schemas.mind_map import (
    GenerateMapRequest,
    GenerateMapResponse,
    MindMapEdge,
    MindMapNode,
    MindMapNodeData,
)


def test_mind_map_pydantic_contracts_validation() -> None:
    """Validate that Pydantic schemas enforce strict contract rules."""
    node = MindMapNode(
        id="node-1",
        type="input",
        data=MindMapNodeData(
            label="Photosynthesis",
            summary="Process by which plants convert light energy into chemical energy.",
            category="root",
        ),
    )
    edge = MindMapEdge(
        id="edge-1",
        source="node-1",
        target="node-2",
        label="produces",
    )
    response = GenerateMapResponse(
        topic="Photosynthesis",
        nodes=[node],
        edges=[edge],
        source_chunks_used=2,
    )
    assert response.topic == "Photosynthesis"
    assert len(response.nodes) == 1
    assert response.nodes[0].data.label == "Photosynthesis"
    assert response.edges[0].source == "node-1"


def test_generate_map_request_rejects_short_query() -> None:
    """Ensure GenerateMapRequest rejects queries shorter than 3 characters."""
    with pytest.raises(ValidationError):
        GenerateMapRequest(query="ab")


@pytest.mark.asyncio
async def test_generate_map_endpoint_returns_valid_contract(
    async_client: AsyncClient,
) -> None:
    """Verify POST /api/generate-map returns a valid GenerateMapResponse payload."""
    payload = {"query": "Neural Networks and Deep Learning", "top_k": 5}
    response = await async_client.post("/api/generate-map", json=payload)

    assert response.status_code == 200
    data = response.json()
    validated = GenerateMapResponse.model_validate(data)
    assert validated.topic == "Neural Networks and Deep Learning"
    assert len(validated.nodes) >= 1
    assert len(validated.edges) >= 1

