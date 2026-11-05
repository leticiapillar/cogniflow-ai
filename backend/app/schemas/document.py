from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class IngestedChunkPayload:
    """Processed chunk with its text, source location, and vector embedding."""

    chunk_index: int
    content: str
    section_title: str | None
    page_start: int
    page_end: int
    embedding: list[float]


@dataclass(frozen=True)
class IngestionResult:
    """Output of the ingestion pipeline, ready to be persisted."""

    page_count: int
    chunks: list[IngestedChunkPayload]


class DocumentChunkSchema(BaseModel):
    """Schema representing a vectorized text chunk from an ingested document."""

    id: UUID = Field(..., description="Unique identifier of the document chunk.")
    document_name: str = Field(..., min_length=1, description="Source document filename.")
    chunk_index: int = Field(..., ge=0, description="Zero-based index of the chunk.")
    content: str = Field(..., min_length=1, description="Extracted text content.")
    section_title: str | None = Field(
        default=None, description="Title of the section the chunk belongs to, if detected."
    )
    page_start: int = Field(..., ge=1, description="First PDF page covered by the chunk.")
    page_end: int = Field(..., ge=1, description="Last PDF page covered by the chunk.")
    created_at: datetime = Field(..., description="Timestamp when chunk was stored.")


class DocumentUploadResponse(BaseModel):
    """Response contract returned after document ingestion and vectorization."""

    document_id: UUID = Field(..., description="Identifier of the stored document.")
    document_name: str = Field(..., description="Processed document filename.")
    page_count: int = Field(..., ge=1, description="Number of pages in the PDF.")
    total_chunks: int = Field(..., ge=0, description="Number of semantic chunks stored.")
    message: str = Field(..., description="Human-readable status message.")
