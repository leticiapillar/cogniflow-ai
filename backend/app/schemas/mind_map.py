from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.services.sanitizer import sanitize_text_input


class NodePosition(BaseModel):
    """2D canvas coordinates for React Flow nodes (auto-calculated via Dagre on frontend)."""

    x: float = Field(default=0.0, description="Horizontal coordinate on canvas.")
    y: float = Field(default=0.0, description="Vertical coordinate on canvas.")


class MindMapNodeData(BaseModel):
    """Payload inside a React Flow mind map node."""

    label: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Concise title of the concept.",
    )
    summary: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Accessible, simplified explanation of the concept.",
    )
    category: Optional[str] = Field(
        default="concept",
        description="Semantic category of the node (e.g., root, topic, concept, example).",
    )


class MindMapNode(BaseModel):
    """Strict contract for a React Flow node."""

    id: str = Field(..., min_length=1, description="Unique identifier for the node.")
    type: str = Field(
        default="default",
        description="React Flow node type (e.g., input, default, output, custom).",
    )
    data: MindMapNodeData = Field(..., description="Visual and semantic node data.")
    position: NodePosition = Field(
        default_factory=NodePosition,
        description="Initial coordinates before auto-layout calculation.",
    )


class MindMapEdge(BaseModel):
    """Strict contract for a directed connection (edge) between two React Flow nodes."""

    id: str = Field(..., min_length=1, description="Unique identifier for the edge.")
    source: str = Field(..., min_length=1, description="ID of the origin node.")
    target: str = Field(..., min_length=1, description="ID of the destination node.")
    label: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Semantic relationship label connecting source and target.",
    )
    animated: bool = Field(
        default=False, description="Whether the edge is visually animated."
    )


class GenerateMapRequest(BaseModel):
    """Request contract for `/api/generate-map`."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Topic or question to generate the visual mind map from.",
    )
    document_name: Optional[str] = Field(
        default=None,
        description="Optional filter to restrict RAG retrieval to a specific document.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of relevant semantic chunks to retrieve from pgvector.",
    )

    @field_validator("query")
    @classmethod
    def sanitize_and_validate_query(cls, value: str) -> str:
        """Sanitize query text and block prompt injection attempts."""
        return sanitize_text_input(value, reject_on_injection=True)


class GenerateMapResponse(BaseModel):
    """Strict JSON output contract for `/api/generate-map` consumed by React Flow."""

    topic: str = Field(..., min_length=1, description="Main topic of the mind map.")
    nodes: List[MindMapNode] = Field(
        ..., min_length=1, description="List of mind map concept nodes."
    )
    edges: List[MindMapEdge] = Field(
        default_factory=list,
        description="List of directed edges connecting the nodes.",
    )
    source_chunks_used: int = Field(
        default=0,
        ge=0,
        description="Count of retrieved document chunks used as grounding context.",
    )
    generation_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="End-to-end RAG + LLM generation latency in milliseconds.",
    )
