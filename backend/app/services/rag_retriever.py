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
        neighbor_window: int = 1,
    ) -> Sequence[DocumentChunkModel]:
        """Embed the query, retrieve top-K chunks, expand neighbor context, and sort canonically."""
        query_embedding = await self._embedding_service.aembed_query(query)
        primary_chunks = list(
            await self._repository.search_similar_chunks(
                query_embedding=query_embedding,
                top_k=top_k,
                document_name=document_name,
            )
        )
        if not primary_chunks:
            return []

        merged_by_key: dict[tuple[str, int], DocumentChunkModel] = {
            (chunk.document_name, chunk.chunk_index): chunk
            for chunk in primary_chunks
        }

        if neighbor_window > 0 and hasattr(self._repository, "get_chunks_by_indices"):
            indices_by_doc: dict[str, set[int]] = {}
            for chunk in primary_chunks:
                doc_indices = indices_by_doc.setdefault(chunk.document_name, set())
                for offset in range(-neighbor_window, neighbor_window + 1):
                    candidate_idx = chunk.chunk_index + offset
                    if (
                        candidate_idx >= 0
                        and (chunk.document_name, candidate_idx) not in merged_by_key
                    ):
                        doc_indices.add(candidate_idx)

            max_expanded = max(top_k, top_k * 2 + 2)
            for doc_name, missing_indices in indices_by_doc.items():
                if not missing_indices or len(merged_by_key) >= max_expanded:
                    continue
                neighbor_chunks = await self._repository.get_chunks_by_indices(
                    document_name=doc_name,
                    chunk_indices=sorted(missing_indices),
                )
                for neighbor in neighbor_chunks:
                    if len(merged_by_key) >= max_expanded:
                        break
                    merged_by_key[(neighbor.document_name, neighbor.chunk_index)] = (
                        neighbor
                    )

        # Stratified section coverage when a specific document is targeted and broader coverage is requested
        if (
            document_name
            and top_k >= 10
            and hasattr(self._repository, "get_chunks_by_document")
        ):
            all_doc_chunks = list(
                await self._repository.get_chunks_by_document(document_name)
            )
            target_budget = min(len(all_doc_chunks), max(top_k, int(top_k * 1.3)))
            if len(all_doc_chunks) <= target_budget:
                for chunk in all_doc_chunks:
                    merged_by_key[(chunk.document_name, chunk.chunk_index)] = chunk
            elif len(merged_by_key) < target_budget and len(all_doc_chunks) > 0:
                step = max(1, len(all_doc_chunks) // target_budget)
                for idx in range(0, len(all_doc_chunks), step):
                    if len(merged_by_key) >= target_budget:
                        break
                    candidate = all_doc_chunks[idx]
                    merged_by_key[(candidate.document_name, candidate.chunk_index)] = (
                        candidate
                    )

        ordered_chunks = sorted(
            merged_by_key.values(),
            key=lambda item: (item.document_name, item.chunk_index),
        )
        logger.info(
            "Retrieved %d relevant chunks (primary=%d, expanded=%d) for query='%s' (document_filter=%s).",
            len(ordered_chunks),
            len(primary_chunks),
            len(ordered_chunks) - len(primary_chunks),
            query,
            document_name,
        )
        return ordered_chunks

