import logging

from app.core.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentChunkSchema, DocumentUploadResponse
from app.services.ingestion_pipeline import IngestionOrchestrator
from app.services.sanitizer import validate_pdf_upload

logger = logging.getLogger("cogniflow.use_cases.ingest_document")


class IngestDocumentUseCase:
    """Use case orchestrating PDF validation, parsing, chunking, embedding, and pgvector storage."""

    def __init__(
        self,
        repository: DocumentRepository,
        orchestrator: IngestionOrchestrator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings or get_settings()
        self._orchestrator = orchestrator or IngestionOrchestrator(
            settings=self._settings
        )

    async def execute_pdf_upload(
        self,
        filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> DocumentUploadResponse:
        """Validate, parse, chunk, vectorize, and store a PDF document in pgvector."""
        safe_filename = validate_pdf_upload(
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            max_size_bytes=self._settings.max_pdf_size_bytes,
        )

        embedded_chunks = await self._orchestrator.process_pdf_bytes(file_bytes)
        stored_models = await self._repository.replace_document_chunks(
            document_name=safe_filename,
            chunks=embedded_chunks,
        )

        return DocumentUploadResponse(
            document_name=safe_filename,
            total_chunks=len(stored_models),
            message=f"Successfully ingested and vectorized {len(stored_models)} chunks.",
        )

    async def list_document_chunks(
        self, document_name: str
    ) -> list[DocumentChunkSchema]:
        """Return stored chunks for a document."""
        records = await self._repository.get_chunks_by_document(document_name)
        return [DocumentChunkSchema.model_validate(record) for record in records]

