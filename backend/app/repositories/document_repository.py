import logging
from typing import Sequence
import uuid

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import (
    SECTION_TITLE_MAX_LENGTH,
    DocumentChunkModel,
    DocumentModel,
)
from app.schemas.document import IngestedChunkPayload

logger = logging.getLogger("cogniflow.repository")

MIGRATION_HINT = (
    "Run backend/scripts/migrate_03.sql, restart the backend, and re-ingest the PDFs."
)


class DocumentRepository:
    """Repository encapsulating PostgreSQL and pgvector operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def check_connection(self) -> bool:
        """Verify database and pgvector extension readiness."""
        try:
            result = await self._session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            extension_name = result.scalar_one_or_none()
            return extension_name == "vector"
        except Exception as exc:
            logger.error("Database connection check failed: %s", exc)
            return False

    async def check_schema(self, expected_dimension: int) -> list[str]:
        """Report schema problems, e.g. a legacy table left over from a previous version."""
        columns = await self._session.execute(
            text(
                "SELECT attname, atttypmod FROM pg_attribute "
                "WHERE attrelid = to_regclass('document_chunks') "
                "AND attnum > 0 AND NOT attisdropped"
            )
        )
        column_typmods = {name: typmod for name, typmod in columns.all()}
        if not column_typmods:
            return ["Table 'document_chunks' does not exist. Restart the backend to create it."]
        if "document_id" not in column_typmods:
            return [f"Table 'document_chunks' uses a legacy schema. {MIGRATION_HINT}"]
        dimension = column_typmods.get("embedding")
        if dimension != expected_dimension:
            return [
                f"Column 'document_chunks.embedding' has {dimension} dimensions, "
                f"but EMBEDDING_DIMENSION={expected_dimension}. {MIGRATION_HINT}"
            ]
        return []

    async def get_document_by_name(self, name: str) -> DocumentModel | None:
        result = await self._session.execute(
            select(DocumentModel).where(DocumentModel.name == name)
        )
        return result.scalar_one_or_none()

    async def replace_document(
        self,
        name: str,
        sha256: str,
        page_count: int,
        embedding_model: str,
        embedding_dimension: int,
        chunks: Sequence[IngestedChunkPayload],
    ) -> tuple[DocumentModel, list[DocumentChunkModel]]:
        """Atomically replace a document (and its chunks) by name."""
        try:
            await self._session.execute(
                delete(DocumentModel).where(DocumentModel.name == name)
            )
            document = DocumentModel(
                id=uuid.uuid4(),
                name=name,
                sha256=sha256,
                page_count=page_count,
                embedding_model=embedding_model,
                embedding_dimension=embedding_dimension,
            )
            self._session.add(document)
            await self._session.flush()

            chunk_models = [
                DocumentChunkModel(
                    document_id=document.id,
                    chunk_index=item.chunk_index,
                    content=item.content,
                    section_title=(
                        item.section_title[:SECTION_TITLE_MAX_LENGTH]
                        if item.section_title
                        else None
                    ),
                    page_start=item.page_start,
                    page_end=item.page_end,
                    embedding=item.embedding,
                )
                for item in chunks
            ]
            self._session.add_all(chunk_models)
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

        await self._session.refresh(document)
        for model in chunk_models:
            await self._session.refresh(model)
        logger.info(
            "Persisted document '%s' with %d vector chunks (model=%s).",
            name,
            len(chunk_models),
            embedding_model,
        )
        return document, chunk_models

    async def get_chunks_by_document(
        self, document_id: uuid.UUID
    ) -> Sequence[DocumentChunkModel]:
        """Retrieve all stored chunks for a document ordered by chunk_index."""
        statement = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_chunks_by_indices(
        self,
        document_id: uuid.UUID,
        chunk_indices: Sequence[int],
    ) -> Sequence[DocumentChunkModel]:
        """Retrieve specific chunks for a document matching the requested chunk indices."""
        if not chunk_indices:
            return []
        statement = (
            select(DocumentChunkModel)
            .where(
                DocumentChunkModel.document_id == document_id,
                DocumentChunkModel.chunk_index.in_(list(chunk_indices)),
            )
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def search_similar_chunks_with_similarity(
        self,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
    ) -> list[tuple[DocumentChunkModel, float]]:
        """Top-K chunks by cosine distance, each with its cosine similarity (1 - distance).

        Only chunks embedded with `embedding_model` are compared: vectors from other
        models are not comparable with the query vector.
        """
        # With a WHERE filter, a plain HNSW scan can return fewer than top_k rows.
        # Iterative scans (pgvector >= 0.8) keep scanning until enough rows match.
        await self._session.execute(text("SET LOCAL hnsw.iterative_scan = strict_order"))

        distance = DocumentChunkModel.embedding.cosine_distance(query_embedding)
        statement = (
            select(DocumentChunkModel, (1 - distance).label("similarity"))
            .join(DocumentModel, DocumentModel.id == DocumentChunkModel.document_id)
            .where(DocumentModel.embedding_model == embedding_model)
        )
        if document_id is not None:
            statement = statement.where(DocumentChunkModel.document_id == document_id)
        statement = statement.order_by(distance).limit(top_k)

        result = await self._session.execute(statement)
        return [(chunk, float(similarity)) for chunk, similarity in result.all()]

    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
    ) -> list[DocumentChunkModel]:
        """Top-K chunks by cosine distance (see search_similar_chunks_with_similarity)."""
        scored = await self.search_similar_chunks_with_similarity(
            query_embedding, embedding_model, top_k, document_id
        )
        return [chunk for chunk, _ in scored]

    async def get_document(self, document_id: uuid.UUID) -> DocumentModel | None:
        return await self._session.get(DocumentModel, document_id)
