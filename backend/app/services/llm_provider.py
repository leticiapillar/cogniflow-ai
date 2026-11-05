from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.ollama_http import OllamaRequestError, Sleep, post_with_retry

logger = logging.getLogger("cogniflow.services.llm_provider")


class LLMProviderError(RuntimeError):
    """Raised when the LLM provider cannot produce a response."""


class BaseLLMProvider(ABC):
    """Interface for LLM providers producing JSON constrained by a JSON Schema.

    Implementations must never substitute content generated without the model.
    """

    model_name: str

    @abstractmethod
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        """Return the raw JSON text generated for the prompts, following `json_schema`."""


class OllamaLLMProvider(BaseLLMProvider):
    """Local LLM via Ollama's /api/chat with structured outputs (`format` = JSON Schema)."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        max_attempts: int = 3,
        base_delay_seconds: float = 1.0,
    ) -> None:
        self._settings = settings or get_settings()
        self.model_name = self._settings.ollama_llm_model
        self._url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        self._transport = transport
        self._sleep = sleep
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
    ) -> str:
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": json_schema,
            "stream": False,
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_ctx": self._settings.ollama_num_ctx,
                "num_predict": self._settings.ollama_num_predict,
            },
        }
        async with httpx.AsyncClient(
            transport=self._transport,
            timeout=self._settings.ollama_llm_timeout_seconds,
        ) as client:
            try:
                response = await post_with_retry(
                    client,
                    self._url,
                    payload,
                    description=f"LLM '{self.model_name}'",
                    max_attempts=self._max_attempts,
                    base_delay_seconds=self._base_delay_seconds,
                    sleep=self._sleep,
                )
            except OllamaRequestError as exc:
                raise LLMProviderError(str(exc)) from exc

        try:
            return str(response.json()["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected chat response from Ollama: {exc}") from exc


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    """Factory returning the configured LLM provider (Ollama only in this version).

    Extension point: a future provider (e.g. Gemini with `responseSchema`) must implement
    BaseLLMProvider.generate_json.
    """
    active_settings = settings or get_settings()
    if active_settings.llm_provider == "ollama":
        return OllamaLLMProvider(settings=active_settings)
    raise ValueError(f"Unsupported LLM provider '{active_settings.llm_provider}'.")
