import logging
from typing import Sequence

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.models import DocumentChunkModel
from app.schemas.document import IngestedChunkPayload

logger = logging.getLogger("cogniflow.repository")


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

    async def add_chunk(
        self,
        document_name: str,
        chunk_index: int,
        content: str,
        embedding: list[float],
    ) -> DocumentChunkModel:
        """Persist a single document chunk along with its vector embedding."""
        chunk = DocumentChunkModel(
            document_name=document_name,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
        )
        self._session.add(chunk)
        await self._session.commit()
        await self._session.refresh(chunk)
        logger.debug(
            "Stored chunk %d for document '%s' (id=%s).",
            chunk_index,
            document_name,
            chunk.id,
        )
        return chunk

    async def replace_document_chunks(
        self,
        document_name: str,
        chunks: Sequence[IngestedChunkPayload],
    ) -> list[DocumentChunkModel]:
        """Replace existing chunks for a document and persist new embedded chunks in pgvector."""
        await self._session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_name == document_name
            )
        )
        models = [
            DocumentChunkModel(
                document_name=document_name,
                chunk_index=item.chunk_index,
                content=item.content,
                embedding=item.embedding,
            )
            for item in chunks
        ]
        self._session.add_all(models)
        await self._session.commit()
        for model in models:
            await self._session.refresh(model)
        logger.info(
            "Persisted %d vector chunks in pgvector for document '%s'.",
            len(models),
            document_name,
        )
        return models

    async def get_chunks_by_document(
        self, document_name: str
    ) -> Sequence[DocumentChunkModel]:
        """Retrieve all stored chunks for a given document ordered by chunk_index."""
        statement = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_name == document_name)
            .order_by(DocumentChunkModel.chunk_index.asc())
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        document_name: str | None = None,
    ) -> Sequence[DocumentChunkModel]:
        """Retrieve the top-K most similar chunks using pgvector cosine distance."""
        statement = select(DocumentChunkModel)
        if document_name:
            statement = statement.where(
                DocumentChunkModel.document_name == document_name
            )
        statement = statement.order_by(
            DocumentChunkModel.embedding.cosine_distance(query_embedding)
        ).limit(top_k)

        result = await self._session.execute(statement)
        return result.scalars().all()
