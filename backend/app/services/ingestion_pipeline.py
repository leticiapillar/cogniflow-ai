import logging
from typing import Any

from langchain_core.runnables import RunnableLambda, RunnableSequence

from app.core.config import Settings, get_settings
from app.schemas.document import IngestedChunkPayload
from app.services.chunking import chunk_text_semantically
from app.services.embeddings import EmbeddingService
from app.services.pdf_parser import extract_text_from_pdf_bytes
from app.services.sanitizer import sanitize_text_input

logger = logging.getLogger("cogniflow.services.ingestion_pipeline")


class IngestionOrchestrator:
    """LangChain Runnable pipeline orchestrating PDF extraction, sanitization, chunking, and embedding."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._embedding_service = embedding_service or EmbeddingService(
            settings=self._settings
        )
        self._pipeline: RunnableSequence[dict[str, Any], list[IngestedChunkPayload]] = (
            RunnableLambda(self._extract_step)
            | RunnableLambda(self._sanitize_step)
            | RunnableLambda(self._chunk_step)
            | RunnableLambda(self._embed_step)
        )

    def _extract_step(self, payload: dict[str, Any]) -> str:
        """Step 1: Extract raw text from PDF bytes or direct text input."""
        if "file_bytes" in payload and payload["file_bytes"] is not None:
            return extract_text_from_pdf_bytes(payload["file_bytes"])
        if "raw_text" in payload and payload["raw_text"] is not None:
            return str(payload["raw_text"])
        raise ValueError("Ingestion payload must provide 'file_bytes' or 'raw_text'.")

    def _sanitize_step(self, raw_text: str) -> str:
        """Step 2: Sanitize extracted text and guard against prompt injection."""
        return sanitize_text_input(raw_text, reject_on_injection=True)

    def _chunk_step(self, clean_text: str) -> list[str]:
        """Step 3: Perform semantic chunking by headers and recursive overlap."""
        return chunk_text_semantically(
            text=clean_text,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )

    def _embed_step(self, chunks: list[str]) -> list[IngestedChunkPayload]:
        """Step 4: Generate vector embeddings for all semantic chunks."""
        vectors = self._embedding_service.embed_documents(chunks)
        return [
            IngestedChunkPayload(
                chunk_index=idx,
                content=chunk_content,
                embedding=vector,
            )
            for idx, (chunk_content, vector) in enumerate(
                zip(chunks, vectors, strict=True)
            )
        ]

    async def process_pdf_bytes(self, file_bytes: bytes) -> list[IngestedChunkPayload]:
        """Execute the LangChain ingestion pipeline on a PDF byte stream."""
        result = await self._pipeline.ainvoke({"file_bytes": file_bytes})
        logger.info("Orchestrator produced %d embedded chunks.", len(result))
        return result

    async def process_raw_text(self, raw_text: str) -> list[IngestedChunkPayload]:
        """Execute the LangChain ingestion pipeline on raw text."""
        result = await self._pipeline.ainvoke({"raw_text": raw_text})
        logger.info("Orchestrator produced %d embedded chunks from text.", len(result))
        return result
