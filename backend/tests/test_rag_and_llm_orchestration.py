import uuid

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.repositories.models import EMBEDDING_DIMENSION, DocumentChunkModel
from app.services.llm_provider import OllamaLLMProvider, get_llm_provider
from app.services.rag_retriever import RAGRetriever
from app.services.text_processing import clean_concept_label, reflow_pdf_text_into_sentences
from tests.fakes.embeddings import FakeEmbeddingProvider

DOCUMENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def test_llm_provider_factory_supports_only_ollama() -> None:
    """Only Ollama is selectable; other providers are rejected at configuration time."""
    provider = get_llm_provider(Settings(LLM_PROVIDER="ollama", OLLAMA_LLM_MODEL="qwen2.5:3b"))
    assert isinstance(provider, OllamaLLMProvider)
    assert provider.model_name == "qwen2.5:3b"

    for unsupported in ("local", "gemini", "openai"):
        with pytest.raises(ValidationError, match="Unsupported llm_provider"):
            Settings(LLM_PROVIDER=unsupported)
        with pytest.raises(ValidationError, match="Unsupported embedding_provider"):
            Settings(EMBEDDING_PROVIDER=unsupported)

    assert Settings(LLM_PROVIDER=" Ollama ").llm_provider == "ollama"


def test_text_processing_reflows_pdf_lines_and_drops_metadata() -> None:
    """Wrapped PDF lines are rejoined, author/page lines dropped, labels never dangle."""
    sentences = [
        sentence
        for _, sentence in reflow_pdf_text_into_sentences(
            "Prof. Dr. Marcos Souza\n"
            "## Definição\n"
            "A Inteligência Artificial Generativa (IAG ou\n"
            "GenAI) destaca-se pela\n"
            "sua capacidade de criar conteúdo novo.\n"
            "Página 3"
        )
    ]
    assert sentences == [
        "A Inteligência Artificial Generativa (IAG ou GenAI) destaca-se pela "
        "sua capacidade de criar conteúdo novo."
    ]
    assert clean_concept_label("organelas presentes nas células de") == "Organelas presentes nas células"
    assert clean_concept_label("a capacidade dos seus") == "A capacidade"


class FakeChunkRepository:
    """In-memory repository: vector search returns a fixed ranking with similarities."""

    def __init__(self, count: int, ranking: list[tuple[int, float]]) -> None:
        self.chunks = {
            idx: DocumentChunkModel(
                document_id=DOCUMENT_ID,
                chunk_index=idx,
                content=f"Section {idx} content",
                page_start=1,
                page_end=1,
                embedding=[0.1] * EMBEDDING_DIMENSION,
            )
            for idx in range(count)
        }
        self.ranking = ranking

    async def search_similar_chunks_with_similarity(
        self,
        query_embedding: list[float],
        embedding_model: str,
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
    ) -> list[tuple[DocumentChunkModel, float]]:
        assert embedding_model == "fake-hashed-embedding"
        return [(self.chunks[i], score) for i, score in self.ranking[:top_k]]

    async def get_chunks_by_indices(
        self, document_id: uuid.UUID, chunk_indices: list[int]
    ) -> list[DocumentChunkModel]:
        return [self.chunks[i] for i in sorted(chunk_indices) if i in self.chunks]


def retriever_for(repository: FakeChunkRepository) -> RAGRetriever:
    return RAGRetriever(repository=repository, embedding_provider=FakeEmbeddingProvider())  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_rag_retriever_expands_neighbors_and_orders_canonically() -> None:
    """Hits (4, then 1) plus their neighbors come back in document order."""
    result = await retriever_for(FakeChunkRepository(6, [(4, 0.8), (1, 0.6)])).retrieve(
        "fotossíntese", DOCUMENT_ID, top_k=2
    )

    assert [chunk.chunk_index for chunk in result.chunks] == [0, 1, 2, 3, 4, 5]
    assert result.ranked_indices == [4, 1]
    assert result.best_similarity == 0.8


@pytest.mark.asyncio
async def test_rag_retriever_includes_pinned_chunks_of_a_map_node() -> None:
    result = await retriever_for(FakeChunkRepository(20, [(2, 0.7)])).retrieve(
        "dúvida", DOCUMENT_ID, top_k=1, neighbor_window=0, pinned_indices=[15, 2]
    )
    assert [chunk.chunk_index for chunk in result.chunks] == [2, 15]


@pytest.mark.asyncio
async def test_rag_retriever_budget_keeps_neighbors_of_the_best_hits() -> None:
    """With top_k=1 the budget is 4 chunks: the best hit's neighbors win over the rest."""
    repository = FakeChunkRepository(30, [(20, 0.9)])
    result = await retriever_for(repository).retrieve(
        "dúvida", DOCUMENT_ID, top_k=1, neighbor_window=2
    )
    assert [chunk.chunk_index for chunk in result.chunks] == [18, 19, 20, 21]


@pytest.mark.asyncio
async def test_rag_retriever_without_hits() -> None:
    result = await retriever_for(FakeChunkRepository(3, [])).retrieve("dúvida", DOCUMENT_ID)
    assert result.chunks == [] and result.best_similarity is None
