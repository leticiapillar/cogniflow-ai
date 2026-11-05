import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any

import httpx

logger = logging.getLogger("cogniflow.services.ollama_http")

Sleep = Callable[[float], Awaitable[None]]


class OllamaRequestError(RuntimeError):
    """Raised when an Ollama request fails permanently or after exhausting retries."""


async def post_with_retry(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    *,
    description: str,
    max_attempts: int = 3,
    base_delay_seconds: float = 0.5,
    sleep: Sleep = asyncio.sleep,
) -> httpx.Response:
    """POST to Ollama, retrying with exponential backoff on transient failures only.

    Transient: timeouts, refused or dropped connections, HTTP 5xx (e.g. model loading).
    Client errors (HTTP 4xx, e.g. model not found) fail immediately.
    """
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.post(url, json=payload)
        except httpx.TransportError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code < 400:
                return response
            if response.status_code < 500:
                raise OllamaRequestError(
                    f"Ollama rejected the {description} request "
                    f"(HTTP {response.status_code}): {response.text[:200]}"
                )
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"

        if attempt < max_attempts:
            delay = base_delay_seconds * 2 ** (attempt - 1)
            logger.warning(
                "Ollama %s attempt %d/%d failed (%s); retrying in %.1fs.",
                description,
                attempt,
                max_attempts,
                last_error,
                delay,
            )
            await sleep(delay)

    raise OllamaRequestError(
        f"Ollama {description} is unavailable after {max_attempts} attempts: {last_error}"
    )
