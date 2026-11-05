from collections.abc import Sequence
from dataclasses import dataclass
import logging
import uuid

from app.repositories.document_repository import DocumentRepository
from app.repositories.models import DocumentChunkModel
from app.services.embeddings import BaseEmbeddingProvider

logger = logging.getLogger("cogniflow.services.rag_retriever")


@dataclass(frozen=True)
class RetrievalResult:
    """Chunks to ground an answer, in document order, plus how relevant the best one is."""

    chunks: list[DocumentChunkModel]
    best_similarity: float | None
    # Chunk indices of the vector-search hits, most similar first.
    ranked_indices: list[int]


class RAGRetriever:
    """Semantic retrieval of chunks of one document for the student's questions."""

    def __init__(
        self,
        repository: DocumentRepository,
        embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider

    async def retrieve(
        self,
        query: str,
        document_id: uuid.UUID,
        top_k: int = 5,
        neighbor_window: int = 1,
        pinned_indices: Sequence[int] = (),
    ) -> RetrievalResult:
        """Top-K similar chunks, the always-included `pinned_indices`, and their neighbors.

        Neighbors (chunk_index ± neighbor_window) restore the context a question often
        needs from the sentences right before or after the best match.
        """
        query_embedding = await self._embedding_provider.embed_query(query)
        scored = await self._repository.search_similar_chunks_with_similarity(
            query_embedding=query_embedding,
            embedding_model=self._embedding_provider.model_name,
            top_k=top_k,
            document_id=document_id,
        )
        selected: dict[int, DocumentChunkModel] = {chunk.chunk_index: chunk for chunk, _ in scored}

        pinned = [index for index in pinned_indices if index not in selected]
        if pinned:
            for chunk in await self._repository.get_chunks_by_indices(document_id, pinned):
                selected[chunk.chunk_index] = chunk

        # Neighbors of the best hits first, so the size budget keeps the most useful ones.
        hits = [chunk.chunk_index for chunk, _ in scored] + list(pinned_indices)
        neighbors = list(
            dict.fromkeys(
                hit + offset
                for hit in hits
                for offset in range(-neighbor_window, neighbor_window + 1)
                if offset and hit + offset >= 0 and hit + offset not in selected
            )
        )
        max_chunks = top_k * 2 + 2 + len(pinned)
        budget = max(0, max_chunks - len(selected))
        if neighbors and budget:
            found = {
                chunk.chunk_index: chunk
                for chunk in await self._repository.get_chunks_by_indices(document_id, neighbors)
            }
            for index in neighbors:
                if budget == 0:
                    break
                if index in found:
                    selected[index] = found[index]
                    budget -= 1

        result = RetrievalResult(
            chunks=[selected[index] for index in sorted(selected)],
            best_similarity=scored[0][1] if scored else None,
            ranked_indices=[chunk.chunk_index for chunk, _ in scored],
        )
        logger.info(
            "Retrieved %d chunks (hits=%d, pinned=%d, best_similarity=%s) for document %s.",
            len(result.chunks),
            len(scored),
            len(pinned_indices),
            f"{result.best_similarity:.3f}" if result.best_similarity is not None else "n/a",
            document_id,
        )
        return result
