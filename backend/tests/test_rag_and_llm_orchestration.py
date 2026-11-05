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


@pytest.mark.asyncio
async def test_rag_retriever_expands_neighbor_window_and_orders_canonically() -> None:
    """Verify RAGRetriever expands adjacent chunks and returns results in ascending chunk_index order."""
    dummy_vec = [0.1] * EMBEDDING_DIMENSION
    all_chunks = {
        idx: DocumentChunkModel(
            document_id=DOCUMENT_ID,
            chunk_index=idx,
            content=f"Section {idx} content",
            embedding=dummy_vec,
        )
        for idx in range(6)
    }

    class FakeRepository:
        async def search_similar_chunks(
            self,
            query_embedding: list[float],
            embedding_model: str,
            top_k: int = 5,
            document_id: uuid.UUID | None = None,
        ) -> list[DocumentChunkModel]:
            # Simulate cosine similarity returning out-of-order chunks (4, then 1)
            return [all_chunks[4], all_chunks[1]]

        async def get_chunks_by_indices(
            self,
            document_id: uuid.UUID,
            chunk_indices: list[int],
        ) -> list[DocumentChunkModel]:
            return [all_chunks[i] for i in sorted(chunk_indices) if i in all_chunks]

    retriever = RAGRetriever(
        repository=FakeRepository(),  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider(),
    )
    results = await retriever.retrieve_relevant_chunks(
        query="Generative AI Foundations and History",
        top_k=2,
        document_id=DOCUMENT_ID,
        neighbor_window=1,
    )

    retrieved_indices = [chunk.chunk_index for chunk in results]
    # Primary (4, 1) + neighbors (0, 2, 3, 5) sorted canonically -> [0, 1, 2, 3, 4, 5]
    assert retrieved_indices == [0, 1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_rag_retriever_stratifies_coverage_for_broad_top_k() -> None:
    """Verify RAGRetriever includes chunks across the document when top_k >= 10."""
    dummy_vec = [0.1] * EMBEDDING_DIMENSION
    all_chunks = [
        DocumentChunkModel(
            document_id=DOCUMENT_ID,
            chunk_index=idx,
            content=f"Section {idx} content",
            embedding=dummy_vec,
        )
        for idx in range(12)
    ]

    class BroadFakeRepository:
        async def search_similar_chunks(
            self,
            query_embedding: list[float],
            embedding_model: str,
            top_k: int = 5,
            document_id: uuid.UUID | None = None,
        ) -> list[DocumentChunkModel]:
            return all_chunks[:2]

        async def get_chunks_by_indices(
            self,
            document_id: uuid.UUID,
            chunk_indices: list[int],
        ) -> list[DocumentChunkModel]:
            return [all_chunks[i] for i in sorted(chunk_indices) if 0 <= i < len(all_chunks)]

        async def get_chunks_by_document(
            self,
            document_id: uuid.UUID,
        ) -> list[DocumentChunkModel]:
            return all_chunks

    retriever = RAGRetriever(
        repository=BroadFakeRepository(),  # type: ignore[arg-type]
        embedding_provider=FakeEmbeddingProvider(),
    )
    results = await retriever.retrieve_relevant_chunks(
        query="O que é IAG?",
        top_k=15,
        document_id=DOCUMENT_ID,
    )

    assert [chunk.chunk_index for chunk in results] == list(range(12))
