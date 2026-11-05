import hashlib
import logging

from app.core.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentChunkSchema, DocumentUploadResponse
from app.services.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.services.ingestion_pipeline import IngestionOrchestrator
from app.services.sanitizer import validate_pdf_upload

logger = logging.getLogger("cogniflow.use_cases.ingest_document")


class IngestDocumentUseCase:
    """Use case orchestrating PDF validation, parsing, chunking, embedding, and pgvector storage."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedding_provider: BaseEmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings or get_settings()
        self._embedding_provider = embedding_provider or get_embedding_provider(
            self._settings
        )
        self._orchestrator = IngestionOrchestrator(
            embedding_provider=self._embedding_provider,
            settings=self._settings,
        )

    async def execute_pdf_upload(
        self,
        filename: str,
        content_type: str | None,
        file_bytes: bytes,
    ) -> DocumentUploadResponse:
        """Validate, parse, chunk, and vectorize a PDF, then store it in one transaction.

        Every vector is produced before the database is touched: if the embedding
        provider fails, the previously stored version of the document stays intact.
        """
        safe_filename = validate_pdf_upload(
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            max_size_bytes=self._settings.max_pdf_size_bytes,
        )

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        existing = await self._repository.get_document_by_name(safe_filename)
        if (
            existing is not None
            and existing.sha256 == sha256
            and existing.embedding_model == self._embedding_provider.model_name
            and existing.embedding_dimension == self._embedding_provider.dimension
        ):
            stored = await self._repository.get_chunks_by_document(existing.id)
            logger.info("'%s' is unchanged; reusing its chunks and mind map.", safe_filename)
            return DocumentUploadResponse(
                document_id=existing.id,
                document_name=existing.name,
                page_count=existing.page_count,
                total_chunks=len(stored),
                message="Document already ingested; reusing stored chunks.",
            )

        result = await self._orchestrator.process_pdf_bytes(file_bytes)
        document, stored_chunks = await self._repository.replace_document(
            name=safe_filename,
            sha256=sha256,
            page_count=result.page_count,
            embedding_model=self._embedding_provider.model_name,
            embedding_dimension=self._embedding_provider.dimension,
            chunks=result.chunks,
        )

        return DocumentUploadResponse(
            document_id=document.id,
            document_name=document.name,
            page_count=document.page_count,
            total_chunks=len(stored_chunks),
            message=f"Successfully ingested and vectorized {len(stored_chunks)} chunks.",
        )

    async def list_document_chunks(
        self, document_name: str
    ) -> list[DocumentChunkSchema]:
        """Return stored chunks for a document (empty when the document does not exist)."""
        document = await self._repository.get_document_by_name(document_name)
        if document is None:
            return []
        records = await self._repository.get_chunks_by_document(document.id)
        return [
            DocumentChunkSchema(
                id=record.id,
                document_name=document.name,
                chunk_index=record.chunk_index,
                content=record.content,
                section_title=record.section_title,
                page_start=record.page_start,
                page_end=record.page_end,
                created_at=record.created_at,
            )
            for record in records
        ]
