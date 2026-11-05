import hashlib
import math
import re

from app.repositories.models import EMBEDDING_DIMENSION
from app.services.embeddings import EmbeddingService

TOKEN_REGEX = re.compile(r"[a-zA-ZÀ-ÿ0-9]{2,}")


def hashed_embedding(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    """Deterministic, lexical (non-semantic) vector: tokens and bigrams hashed into buckets."""
    vector = [0.0] * dimension
    tokens = [token.lower() for token in TOKEN_REGEX.findall(text)] or [
        text.strip().lower() or "empty"
    ]
    features = [(tok, 1.0) for tok in tokens]
    features += [(f"{a}_{b}", 1.5) for a, b in zip(tokens, tokens[1:])]
    for feature, weight in features:
        digest = hashlib.sha256(feature.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimension
        vector[bucket] += weight if digest[4] % 2 == 0 else -weight
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else [1.0] + [0.0] * (dimension - 1)


class FakeEmbeddingService(EmbeddingService):
    """Embedding service for tests: deterministic vectors, no network calls."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    def embed_query(self, text: str) -> list[float]:
        return hashed_embedding(text, self._dimension)
