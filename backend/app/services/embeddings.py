from abc import ABC, abstractmethod
import asyncio
from collections.abc import Sequence
import logging

import httpx

from app.core.config import Settings, get_settings
from app.services.ollama_http import OllamaRequestError, Sleep, post_with_retry

logger = logging.getLogger("cogniflow.services.embeddings")


class EmbeddingProviderError(RuntimeError):
    """Raised when the embedding provider cannot produce valid vectors."""


class BaseEmbeddingProvider(ABC):
    """Interface for embedding providers.

    Implementations must never substitute vectors from another model: vectors from
    different models live in incompatible spaces and silently corrupt similarity search.
    """

    model_name: str
    dimension: int

    @abstractmethod
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""

    async def embed_query(self, text: str) -> list[float]:
        """Return the vector for a single query text."""
        return (await self.embed_documents([text]))[0]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Embeddings from a local Ollama server via the batched /api/embed endpoint."""

    REQUEST_TIMEOUT_SECONDS = 120.0

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        batch_size: int = 16,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
    ) -> None:
        active_settings = settings or get_settings()
        self.model_name = active_settings.ollama_embedding_model
        self.dimension = active_settings.embedding_dimension
        self._url = f"{active_settings.ollama_base_url.rstrip('/')}/api/embed"
        self._transport = transport
        self._sleep = sleep
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(
            transport=self._transport, timeout=self.REQUEST_TIMEOUT_SECONDS
        ) as client:
            for start in range(0, len(texts), self._batch_size):
                batch = list(texts[start : start + self._batch_size])
                vectors.extend(await self._embed_batch(client, batch))
        return vectors

    async def _embed_batch(
        self, client: httpx.AsyncClient, batch: list[str]
    ) -> list[list[float]]:
        """Embed one batch, retrying transient failures (never substituting another model)."""
        try:
            response = await post_with_retry(
                client,
                self._url,
                {"model": self.model_name, "input": batch},
                description=f"embedding model '{self.model_name}'",
                max_attempts=self._max_attempts,
                base_delay_seconds=self._base_delay_seconds,
                sleep=self._sleep,
            )
        except OllamaRequestError as exc:
            raise EmbeddingProviderError(str(exc)) from exc
        return self._parse_vectors(response, expected_count=len(batch))

    def _parse_vectors(
        self, response: httpx.Response, expected_count: int
    ) -> list[list[float]]:
        try:
            vectors = response.json()["embeddings"]
        except (ValueError, KeyError, TypeError) as exc:
            raise EmbeddingProviderError(
                f"Unexpected embedding response from Ollama: {exc}"
            ) from exc

        if len(vectors) != expected_count:
            raise EmbeddingProviderError(
                f"Ollama returned {len(vectors)} vectors for {expected_count} inputs."
            )
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingProviderError(
                    f"Embedding model '{self.model_name}' returned {len(vector)} dimensions, "
                    f"but EMBEDDING_DIMENSION={self.dimension}."
                )
        return [[float(value) for value in vector] for vector in vectors]


def get_embedding_provider(settings: Settings | None = None) -> BaseEmbeddingProvider:
    """Factory returning the configured embedding provider (Ollama only in this version).

    Extension point: a future Gemini provider must implement BaseEmbeddingProvider and
    produce vectors with EMBEDDING_DIMENSION dimensions.
    """
    active_settings = settings or get_settings()
    if active_settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(settings=active_settings)
    raise ValueError(f"Unsupported embedding provider '{active_settings.embedding_provider}'.")
