import logging
from typing import Sequence

from app.repositories.document_repository import DocumentRepository
from app.repositories.models import DocumentChunkModel
from app.services.embeddings import EmbeddingService

logger = logging.getLogger("cogniflow.services.rag_retriever")


class RAGRetriever:
    """Service responsible for semantic vector similarity retrieval from pgvector."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_service = embedding_service or EmbeddingService()

    async def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        document_name: str | None = None,
    ) -> Sequence[DocumentChunkModel]:
        """Embed the query and retrieve the top-K most relevant chunks via cosine similarity."""
        query_embedding = await self._embedding_service.aembed_query(query)
        chunks = await self._repository.search_similar_chunks(
            query_embedding=query_embedding,
            top_k=top_k,
            document_name=document_name,
        )
        logger.info(
            "Retrieved %d relevant chunks for query='%s' (document_filter=%s).",
            len(chunks),
            query,
            document_name,
        )
        return chunks

