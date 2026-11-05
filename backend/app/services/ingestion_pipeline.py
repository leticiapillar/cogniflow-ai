import logging

from langchain_core.runnables import RunnableLambda, RunnableSequence

from app.core.config import Settings, get_settings
from app.schemas.document import IngestedChunkPayload, IngestionResult
from app.services.chunking import TextChunk, chunk_pages
from app.services.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.services.pdf_parser import ParsedPdf, PdfPage, parse_pdf
from app.services.sanitizer import InputValidationError, sanitize_text_input

logger = logging.getLogger("cogniflow.services.ingestion_pipeline")


class IngestionOrchestrator:
    """LangChain Runnable pipeline: PDF extraction, sanitization, chunking, and embedding.

    The pipeline only computes; it never writes to the database. Persisting happens after
    every vector has been produced, so a provider failure never leaves a partial document.
    """

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._embedding_provider = embedding_provider or get_embedding_provider(
            self._settings
        )
        self._pipeline: RunnableSequence[bytes, IngestionResult] = (
            RunnableLambda(self._extract_step)
            | RunnableLambda(self._sanitize_step)
            | RunnableLambda(self._chunk_step)
            | RunnableLambda(self._embed_step)
        )

    def _extract_step(self, file_bytes: bytes) -> ParsedPdf:
        """Step 1: Extract the text of each PDF page."""
        return parse_pdf(file_bytes)

    def _sanitize_step(self, parsed: ParsedPdf) -> ParsedPdf:
        """Step 2: Sanitize each page and guard against prompt injection."""
        pages = [
            PdfPage(number=page.number, text=cleaned)
            for page in parsed.pages
            if (cleaned := sanitize_text_input(page.text, reject_on_injection=True))
        ]
        if not pages:
            raise InputValidationError("The PDF has no usable text after sanitization.")
        return ParsedPdf(pages=pages, page_count=parsed.page_count)

    def _chunk_step(self, parsed: ParsedPdf) -> tuple[int, list[TextChunk]]:
        """Step 3: Chunk by section headings and size, keeping section and page ranges."""
        chunks = chunk_pages(
            parsed.pages,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )
        return parsed.page_count, chunks

    async def _embed_step(self, chunked: tuple[int, list[TextChunk]]) -> IngestionResult:
        """Step 4: Embed every chunk (fails as a whole if the provider fails)."""
        page_count, chunks = chunked
        vectors = await self._embedding_provider.embed_documents(
            [chunk.content for chunk in chunks]
        )
        return IngestionResult(
            page_count=page_count,
            chunks=[
                IngestedChunkPayload(
                    chunk_index=idx,
                    content=chunk.content,
                    section_title=chunk.section_title,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    embedding=vector,
                )
                for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ],
        )

    async def process_pdf_bytes(self, file_bytes: bytes) -> IngestionResult:
        """Execute the ingestion pipeline on a PDF byte stream."""
        result = await self._pipeline.ainvoke(file_bytes)
        logger.info(
            "Orchestrator produced %d embedded chunks from %d pages.",
            len(result.chunks),
            result.page_count,
        )
        return result
