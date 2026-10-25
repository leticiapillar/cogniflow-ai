from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class IngestedChunkPayload:
    """Processed chunk with its text content, index, and vector embedding."""

    chunk_index: int
    content: str
    embedding: list[float]


class DocumentChunkSchema(BaseModel):
    """Schema representing a vectorized text chunk from an ingested document."""

    id: UUID = Field(..., description="Unique identifier of the document chunk.")
    document_name: str = Field(..., min_length=1, description="Source document filename.")
    chunk_index: int = Field(..., ge=0, description="Zero-based index of the chunk.")
    content: str = Field(..., min_length=1, description="Extracted text content.")
    created_at: datetime = Field(..., description="Timestamp when chunk was stored.")

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    """Response contract returned after document ingestion and vectorization."""

    document_name: str = Field(..., description="Processed document filename.")
    total_chunks: int = Field(..., ge=0, description="Number of semantic chunks stored.")
    message: str = Field(..., description="Human-readable status message.")
