from collections.abc import Callable, Iterator

import httpx
import pytest

from app.core.config import Settings
from app.services.ollama_readiness import (
    OllamaReadiness,
    check_ollama_readiness,
    clear_dimension_cache,
)
from app.use_cases.health_check import HealthCheckUseCase

SETTINGS = Settings(
    OLLAMA_BASE_URL="http://ollama.test",
    OLLAMA_EMBEDDING_MODEL="bge-m3",
    OLLAMA_LLM_MODEL="llama3.2:3b",
    EMBEDDING_DIMENSION=1024,
)


@pytest.fixture(autouse=True)
def reset_dimension_cache() -> Iterator[None]:
    clear_dimension_cache()
    yield
    clear_dimension_cache()


def fake_ollama(
    installed: list[str],
    dimension: int = 1024,
    calls: list[str] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request.url.path)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": n} for n in installed]})
        if request.url.path == "/api/embed":
            return httpx.Response(200, json={"embeddings": [[0.1] * dimension]})
        return httpx.Response(404)

    return handler


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_ready_when_models_installed_and_dimension_matches() -> None:
    async with client_for(fake_ollama(["bge-m3:latest", "llama3.2:3b"])) as client:
        result = await check_ollama_readiness(SETTINGS, client=client)

    assert result.ready
    assert result.reachable
    assert result.missing_models == []
    assert result.embedding_dimension == 1024


async def test_reports_missing_models_and_skips_embedding_probe() -> None:
    calls: list[str] = []
    async with client_for(fake_ollama(["llama3.2:1b"], calls=calls)) as client:
        result = await check_ollama_readiness(SETTINGS, client=client)

    assert not result.ready
    assert result.reachable
    assert result.missing_models == ["bge-m3", "llama3.2:3b"]
    assert "/api/embed" not in calls


async def test_reports_dimension_mismatch() -> None:
    handler = fake_ollama(["bge-m3:latest", "llama3.2:3b"], dimension=768)
    async with client_for(handler) as client:
        result = await check_ollama_readiness(SETTINGS, client=client)

    assert not result.ready
    assert result.embedding_dimension == 768
    assert "768 dimensions" in result.issues[0]


async def test_reports_unreachable_server() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with client_for(refuse) as client:
        result = await check_ollama_readiness(SETTINGS, client=client)

    assert not result.ready
    assert not result.reachable
    assert "unreachable" in result.issues[0]


async def test_caches_probed_dimension() -> None:
    calls: list[str] = []
    handler = fake_ollama(["bge-m3:latest", "llama3.2:3b"], calls=calls)
    async with client_for(handler) as client:
        await check_ollama_readiness(SETTINGS, client=client)
        await check_ollama_readiness(SETTINGS, client=client)

    assert calls.count("/api/embed") == 1
    assert calls.count("/api/tags") == 2


class StubRepository:
    def __init__(self, connected: bool) -> None:
        self._connected = connected

    async def check_connection(self) -> bool:
        return self._connected


@pytest.mark.parametrize(
    ("db_connected", "readiness", "expected_status", "expected_issues"),
    [
        (True, OllamaReadiness(reachable=True, embedding_dimension=1024), "healthy", 0),
        (True, OllamaReadiness(issues=["Ollama server is unreachable"]), "degraded", 1),
        (False, OllamaReadiness(reachable=True, embedding_dimension=1024), "degraded", 1),
        (False, OllamaReadiness(issues=["Ollama server is unreachable"]), "degraded", 2),
    ],
)
async def test_health_combines_database_and_ollama_readiness(
    db_connected: bool,
    readiness: OllamaReadiness,
    expected_status: str,
    expected_issues: int,
) -> None:
    async def checker(_: Settings) -> OllamaReadiness:
        return readiness

    use_case = HealthCheckUseCase(
        repository=StubRepository(db_connected),  # type: ignore[arg-type]
        settings=SETTINGS,
        readiness_checker=checker,
    )
    response = await use_case.execute()

    assert response.status == expected_status
    assert response.database_connected is db_connected
    assert response.ollama_connected is readiness.reachable
    assert len(response.issues) == expected_issues
