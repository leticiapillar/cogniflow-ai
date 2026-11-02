from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Sequence

import httpx

from app.core.config import Settings, get_settings
from app.services.pedagogical_structurer import (
    build_pedagogical_outline,
    compile_outline_to_mind_map_dict,
    normalize_llm_mind_map_json,
)

logger = logging.getLogger("cogniflow.services.llm_provider")

GEMINI_MIND_MAP_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "required": ["topic", "pedagogical_synthesis", "nodes", "edges"],
    "properties": {
        "topic": {"type": "STRING"},
        "pedagogical_synthesis": {"type": "STRING"},
        "nodes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["id", "type", "data", "position"],
                "properties": {
                    "id": {"type": "STRING"},
                    "type": {
                        "type": "STRING",
                        "enum": ["input", "default"],
                    },
                    "data": {
                        "type": "OBJECT",
                        "required": ["label", "summary", "category"],
                        "properties": {
                            "label": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                            "category": {
                                "type": "STRING",
                                "enum": ["root", "topic", "concept", "example"],
                            },
                        },
                    },
                    "position": {
                        "type": "OBJECT",
                        "required": ["x", "y"],
                        "properties": {
                            "x": {"type": "NUMBER"},
                            "y": {"type": "NUMBER"},
                        },
                    },
                },
            },
        },
        "edges": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "required": ["id", "source", "target", "label", "animated"],
                "properties": {
                    "id": {"type": "STRING"},
                    "source": {"type": "STRING"},
                    "target": {"type": "STRING"},
                    "label": {"type": "STRING"},
                    "animated": {"type": "BOOLEAN"},
                },
            },
        },
    },
}

MARKDOWN_HEADER_LINE_REGEX = re.compile(r"^\s*#{1,4}\s+(?P<title>.+)$")


class BaseLLMProvider(ABC):
    """Abstract base interface for LLM mind map generation providers."""

    @abstractmethod
    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Generate a strict JSON mind map representation from RAG context."""


class ContextGroundedLocalLLMProvider(BaseLLMProvider):
    """Deterministic, context-grounded JSON generator extracting concepts via pedagogical structuring."""

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Synthesize and structure retrieved chunks into a pedagogical hierarchy compiled to strict JSON."""
        outline = build_pedagogical_outline(
            query=query,
            context_chunks=context_chunks,
            max_concepts=12,
        )
        payload = compile_outline_to_mind_map_dict(outline)
        return json.dumps(payload, ensure_ascii=False)


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini API provider configured for strict JSON Mode output."""

    FALLBACK_MODELS: tuple[str, ...] = (
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
    )

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._fallback = ContextGroundedLocalLLMProvider()

    def _candidate_models(self) -> list[str]:
        """Return the configured model followed by fallback Gemini models without duplicates."""
        primary = self._settings.gemini_model.removeprefix("models/")
        candidates = [primary]
        for model in self.FALLBACK_MODELS:
            if model not in candidates:
                candidates.append(model)
        return candidates

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Invoke Gemini generateContent API with responseMimeType='application/json'."""
        if not self._settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY is not set; using ContextGroundedLocalLLMProvider."
            )
            return await self._fallback.generate_mind_map_json(
                system_prompt, user_prompt, query, context_chunks
            )

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": self._settings.llm_temperature,
                "responseMimeType": "application/json",
                "responseSchema": GEMINI_MIND_MAP_RESPONSE_SCHEMA,
                "maxOutputTokens": 4096,
            },
        }

        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=60.0) as client:
            for model_name in self._candidate_models():
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_name}:generateContent?key={self._settings.gemini_api_key}"
                )
                try:
                    response = await client.post(url, json=payload)
                    if response.status_code in {404, 429, 500, 502, 503, 504}:
                        logger.warning(
                            "Gemini model '%s' returned HTTP %d; trying next candidate model.",
                            model_name,
                            response.status_code,
                        )
                        response.raise_for_status()
                    response.raise_for_status()
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return normalize_llm_mind_map_json(
                        raw_output=raw_text,
                        query=query,
                        context_chunks=context_chunks,
                    )
                except Exception as exc:
                    last_exc = exc
                    continue

        logger.warning(
            "Gemini LLM request failed across candidate models (%s); falling back to ContextGroundedLocalLLMProvider.",
            last_exc,
        )
        return await self._fallback.generate_mind_map_json(
            system_prompt, user_prompt, query, context_chunks
        )


class OllamaLLMProvider(BaseLLMProvider):
    """Local open-source LLM provider via Ollama configured for strict JSON mode."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._fallback = ContextGroundedLocalLLMProvider()

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Invoke local Ollama /api/chat endpoint with format='json' and local fallback."""
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self._settings.ollama_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": self._settings.llm_temperature,
                "num_ctx": 8192,
                "num_predict": 2500,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                raw_text = data["message"]["content"]
                return normalize_llm_mind_map_json(
                    raw_output=raw_text,
                    query=query,
                    context_chunks=context_chunks,
                )
        except Exception as exc:
            logger.warning(
                "Ollama LLM request failed or timed out (%s); falling back to ContextGroundedLocalLLMProvider.",
                exc,
            )
            return await self._fallback.generate_mind_map_json(
                system_prompt, user_prompt, query, context_chunks
            )


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    """Factory returning the configured LLM provider instance (Gemini, Ollama, or Local)."""
    active_settings = settings or get_settings()
    provider_name = active_settings.llm_provider.strip().lower()

    if provider_name == "gemini":
        return GeminiLLMProvider(settings=active_settings)
    if provider_name == "ollama":
        return OllamaLLMProvider(settings=active_settings)
    return ContextGroundedLocalLLMProvider()

