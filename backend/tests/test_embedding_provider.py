from collections.abc import Callable
import json

import httpx
import pytest

from app.core.config import Settings
from app.services.embeddings import (
    EmbeddingProviderError,
    OllamaEmbeddingProvider,
    get_embedding_provider,
)

SETTINGS = Settings(
    OLLAMA_BASE_URL="http://ollama.test",
    OLLAMA_EMBEDDING_MODEL="bge-m3",
    EMBEDDING_DIMENSION=4,
)

Handler = Callable[[httpx.Request], httpx.Response]


def build_provider(handler: Handler, sleeps: list[float] | None = None, **kwargs: int):
    async def record_sleep(delay: float) -> None:
        if sleeps is not None:
            sleeps.append(delay)

    return OllamaEmbeddingProvider(
        SETTINGS,
        transport=httpx.MockTransport(handler),
        sleep=record_sleep,
        **kwargs,
    )


def echo_vectors(request: httpx.Request) -> httpx.Response:
    inputs = json.loads(request.content)["input"]
    return httpx.Response(
        200, json={"embeddings": [[float(len(text)), 0.0, 0.0, 1.0] for text in inputs]}
    )


async def test_embeds_in_batches_preserving_order() -> None:
    batches: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["model"] == "bge-m3"
        batches.append(body["input"])
        return echo_vectors(request)

    provider = build_provider(handler, batch_size=2)
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]
    vectors = await provider.embed_documents(texts)

    assert batches == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert provider.model_name == "bge-m3"
    assert provider.dimension == 4


async def test_retries_transient_errors_with_exponential_backoff() -> None:
    responses = iter([503, 500])
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(responses, 200)
        if status != 200:
            return httpx.Response(status, text="loading model")
        return echo_vectors(request)

    provider = build_provider(handler, sleeps=sleeps)
    vectors = await provider.embed_documents(["texto"])

    assert len(vectors) == 1
    assert sleeps == [0.5, 1.0]


async def test_raises_after_exhausting_retries_on_connection_errors() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection refused", request=request)

    provider = build_provider(handler, sleeps=sleeps)
    with pytest.raises(EmbeddingProviderError, match="after 3 attempts"):
        await provider.embed_documents(["texto"])

    assert attempts == 3
    assert sleeps == [0.5, 1.0]


async def test_does_not_retry_client_errors() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"error": "model 'bge-m3' not found"})

    provider = build_provider(handler)
    with pytest.raises(EmbeddingProviderError, match="HTTP 404"):
        await provider.embed_documents(["texto"])
    assert attempts == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"embeddings": [[0.1, 0.2]]},  # wrong dimension
        {"embeddings": []},  # wrong vector count
        {"unexpected": True},  # malformed body
    ],
)
async def test_rejects_invalid_vectors(payload: dict[str, object]) -> None:
    provider = build_provider(lambda request: httpx.Response(200, json=payload))
    with pytest.raises(EmbeddingProviderError):
        await provider.embed_documents(["texto"])


async def test_empty_input_makes_no_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert await build_provider(handler).embed_documents([]) == []


async def test_embed_query_returns_single_vector() -> None:
    vector = await build_provider(echo_vectors).embed_query("abc")
    assert vector == [3.0, 0.0, 0.0, 1.0]


def test_factory_returns_ollama_provider() -> None:
    assert isinstance(get_embedding_provider(SETTINGS), OllamaEmbeddingProvider)
