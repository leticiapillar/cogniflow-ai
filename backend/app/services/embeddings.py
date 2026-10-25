import hashlib
import logging
import math
import re

import httpx
from langchain_core.embeddings import Embeddings

from app.core.config import Settings, get_settings
from app.repositories.models import EMBEDDING_DIMENSION

logger = logging.getLogger("cogniflow.services.embeddings")

TOKEN_REGEX = re.compile(r"[a-zA-ZÀ-ÿ0-9]{2,}")


def _compute_deterministic_embedding(
    text: str, dimension: int = EMBEDDING_DIMENSION
) -> list[float]:
    """Compute a normalized feature-hashed vector from word tokens and bigrams."""
    vector = [0.0] * dimension
    tokens = [token.lower() for token in TOKEN_REGEX.findall(text)]
    if not tokens:
        tokens = [text.strip().lower() or "empty"]

    features: list[tuple[str, float]] = [(tok, 1.0) for tok in tokens]
    for idx in range(len(tokens) - 1):
        features.append((f"{tokens[idx]}_{tokens[idx + 1]}", 1.5))

    for feature, weight in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if (digest[4] % 2 == 0) else -1.0
        vector[bucket] += sign * weight

    norm = math.sqrt(sum(val * val for val in vector))
    if norm > 0.0:
        vector = [val / norm for val in vector]
    else:
        vector[0] = 1.0
    return vector


def _normalize_and_resize_vector(
    raw_vector: list[float], dimension: int = EMBEDDING_DIMENSION
) -> list[float]:
    """Ensure the vector matches the target pgvector dimension and is L2-normalized."""
    if len(raw_vector) >= dimension:
        resized = raw_vector[:dimension]
    else:
        resized = raw_vector + [0.0] * (dimension - len(raw_vector))
    norm = math.sqrt(sum(val * val for val in resized))
    if norm > 0.0:
        return [val / norm for val in resized]
    return resized


class EmbeddingService(Embeddings):
    """LangChain-compatible embedding service supporting local, Ollama, and Gemini providers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._provider = self._settings.embedding_provider.lower()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a list of document chunks."""
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Generate a 768-dimensional vector embedding for a single text string."""
        if self._provider == "gemini" and self._settings.gemini_api_key:
            return self._embed_with_gemini(text)
        if self._provider == "ollama":
            return self._embed_with_ollama(text)
        return _compute_deterministic_embedding(text, EMBEDDING_DIMENSION)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Asynchronously generate vector embeddings for a list of document chunks."""
        return [await self.aembed_query(text) for text in texts]

    async def aembed_query(self, text: str) -> list[float]:
        """Asynchronously generate a 768-dimensional vector embedding."""
        return self.embed_query(text)

    def _embed_with_gemini(self, text: str) -> list[float]:
        """Request 768-d embedding from Google Gemini API with local fallback."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"text-embedding-004:embedContent?key={self._settings.gemini_api_key}"
        )
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": text}]},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                values = response.json()["embedding"]["values"]
                return _normalize_and_resize_vector(values, EMBEDDING_DIMENSION)
        except Exception as exc:
            logger.warning(
                "Gemini embedding request failed (%s); falling back to local embeddings.",
                exc,
            )
            return _compute_deterministic_embedding(text, EMBEDDING_DIMENSION)

    def _embed_with_ollama(self, text: str) -> list[float]:
        """Request embedding from local Ollama server with deterministic fallback."""
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/embeddings"
        payload = {
            "model": self._settings.ollama_embedding_model,
            "prompt": text,
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                values = response.json()["embedding"]
                return _normalize_and_resize_vector(values, EMBEDDING_DIMENSION)
        except Exception as exc:
            logger.warning(
                "Ollama embedding request failed (%s); falling back to local embeddings.",
                exc,
            )
            return _compute_deterministic_embedding(text, EMBEDDING_DIMENSION)

