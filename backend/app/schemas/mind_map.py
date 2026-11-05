from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

NodeCategory = Literal["root", "topic", "concept", "example"]

RelationType = Literal[
    "has_part",
    "is_a",
    "causes",
    "depends_on",
    "precedes",
    "contrasts",
    "exemplified_by",
]

# One fixed verb per relation type, read from parent to child: the same relation is
# always shown with the same words (predictability for autistic students).
RELATION_LABELS: dict[str, str] = {
    "has_part": "inclui",
    "is_a": "tem como tipo",
    "causes": "produz",
    "depends_on": "depende de",
    "precedes": "vem antes de",
    "contrasts": "contrasta com",
    "exemplified_by": "exemplificado por",
}

MindMapStatus = Literal["pending", "processing", "ready", "partial", "failed"]
MindMapPhase = Literal["pending", "mapping", "consolidating", "organizing", "done"]


class NodePosition(BaseModel):
    """2D canvas coordinates for React Flow nodes (auto-calculated via Dagre on frontend)."""

    x: float = Field(default=0.0, description="Horizontal coordinate on canvas.")
    y: float = Field(default=0.0, description="Vertical coordinate on canvas.")


class MindMapNodeData(BaseModel):
    """Payload inside a React Flow mind map node."""

    label: str = Field(..., min_length=1, max_length=200, description="Concise title (1-6 words).")
    summary: str | None = Field(
        default=None, max_length=1000, description="Literal, short explanation (1-2 sentences)."
    )
    category: NodeCategory = Field(default="concept", description="Level in the hierarchy.")
    order: int | None = Field(
        default=None, ge=1, description="Suggested study order (set on topic nodes)."
    )
    acronyms: dict[str, str] = Field(
        default_factory=dict, description="Acronyms used by the node, already expanded."
    )
    source_chunks: list[int] = Field(
        default_factory=list, description="Indices of the document chunks the node comes from."
    )


class MindMapNode(BaseModel):
    """Strict contract for a React Flow node."""

    id: str = Field(..., min_length=1, description="Unique identifier for the node.")
    type: str = Field(default="default", description="React Flow node type (input for the root).")
    data: MindMapNodeData = Field(..., description="Visual and semantic node data.")
    position: NodePosition = Field(
        default_factory=NodePosition,
        description="Initial coordinates before auto-layout calculation.",
    )


class MindMapEdge(BaseModel):
    """Strict contract for a directed parent -> child connection between two nodes."""

    id: str = Field(..., min_length=1, description="Unique identifier for the edge.")
    source: str = Field(..., min_length=1, description="ID of the parent node.")
    target: str = Field(..., min_length=1, description="ID of the child node.")
    relation: RelationType = Field(..., description="Relation type from the controlled vocabulary.")
    label: str = Field(..., max_length=120, description="Fixed verb shown for the relation.")
    animated: bool = Field(default=False, description="Whether the edge is visually animated.")


class MindMapGraph(BaseModel):
    """Mind map of a whole document as a tree: root -> topics -> concepts -> examples."""

    topic: str = Field(..., min_length=1, description="Central theme of the class material.")
    nodes: list[MindMapNode] = Field(..., min_length=1)
    edges: list[MindMapEdge] = Field(default_factory=list)


class MindMapProgress(BaseModel):
    """Predictable progress information for the generation in course."""

    phase: MindMapPhase
    done: int = Field(..., ge=0, description="Sections already read.")
    total: int = Field(..., ge=0, description="Sections to read.")
    current_section: str | None = Field(default=None)
    message: str = Field(..., description="Literal progress message in Portuguese.")


class FailedSection(BaseModel):
    """A section that could not be processed (left out of a partial map)."""

    section_index: int = Field(..., ge=0)
    section_title: str | None = None
    reason: str


class MindMapStatusResponse(BaseModel):
    """Contract for `GET /api/documents/{document_id}/mind-map`."""

    document_id: UUID
    document_name: str
    status: MindMapStatus
    progress: MindMapProgress
    failed_sections: list[FailedSection] = Field(default_factory=list)
    mind_map: MindMapGraph | None = Field(
        default=None, description="Present when status is 'ready' or 'partial'."
    )
    llm_model: str
    error: str | None = Field(default=None, description="Reason when status is 'failed'.")
    updated_at: datetime
