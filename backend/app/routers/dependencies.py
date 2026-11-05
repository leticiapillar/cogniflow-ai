from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.services.llm_provider import BaseLLMProvider, get_llm_provider


def provide_embedding_provider(
    settings: Settings = Depends(get_settings),
) -> BaseEmbeddingProvider:
    """Dependency provider for the configured embedding provider (overridable in tests)."""
    return get_embedding_provider(settings)


def provide_llm_provider(settings: Settings = Depends(get_settings)) -> BaseLLMProvider:
    """Dependency provider for the configured LLM provider (overridable in tests)."""
    return get_llm_provider(settings)
