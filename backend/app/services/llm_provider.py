from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Sequence

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("cogniflow.services.llm_provider")


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
    """Deterministic, context-grounded JSON generator extracting concepts directly from RAG chunks."""

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Extract key concepts and summaries from retrieved chunks into strict JSON."""
        root_id = "node-root"
        nodes: list[dict[str, object]] = [
            {
                "id": root_id,
                "type": "input",
                "data": {
                    "label": query[:120],
                    "summary": f"Core visual map grounded in {len(context_chunks)} retrieved context block(s).",
                    "category": "root",
                },
                "position": {"x": 0.0, "y": 0.0},
            }
        ]
        edges: list[dict[str, object]] = []

        extracted_items = self._extract_concepts_from_chunks(query, context_chunks)
        for index, (label, summary) in enumerate(extracted_items, start=1):
            node_id = f"node-{index}"
            nodes.append(
                {
                    "id": node_id,
                    "type": "default",
                    "data": {
                        "label": label[:180],
                        "summary": summary[:800],
                        "category": "concept",
                    },
                    "position": {"x": float((index - 1) * 220), "y": 140.0},
                }
            )
            edges.append(
                {
                    "id": f"edge-root-{index}",
                    "source": root_id,
                    "target": node_id,
                    "label": "explains",
                    "animated": False,
                }
            )

        payload = {
            "topic": query,
            "nodes": nodes,
            "edges": edges,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _extract_concepts_from_chunks(
        self, query: str, context_chunks: Sequence[str]
    ) -> list[tuple[str, str]]:
        """Derive structured (label, summary) pairs directly from the retrieved text blocks."""
        if not context_chunks:
            return [
                (
                    f"Overview: {query[:60]}",
                    f"Fundamental concepts related to {query}.",
                )
            ]

        concepts: list[tuple[str, str]] = []
        seen_labels: set[str] = set()

        for chunk in context_chunks:
            lines = [
                line.strip(" #\t●*-")
                for line in chunk.splitlines()
                if line.strip(" #\t●*-")
            ]
            if not lines:
                continue

            for line in lines:
                colon_parts = line.split(":", 1)
                if 1 <= len(colon_parts[0].split()) <= 7 and len(colon_parts) == 2:
                    candidate_label = colon_parts[0].strip()
                    candidate_summary = colon_parts[1].strip() or line
                else:
                    sentences = [
                        s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()
                    ]
                    first_sentence = sentences[0] if sentences else line
                    words = first_sentence.split()
                    candidate_label = " ".join(words[:6]).rstrip(".,;:")
                    candidate_summary = first_sentence

                normalized_key = candidate_label.lower()
                if (
                    len(candidate_label) >= 3
                    and normalized_key not in seen_labels
                ):
                    seen_labels.add(normalized_key)
                    concepts.append((candidate_label, candidate_summary))
                if len(concepts) >= 8:
                    return concepts

        if not concepts:
            concepts.append(
                (
                    "Core Material Concept",
                    context_chunks[0][:300],
                )
            )
        return concepts


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini API provider configured for strict JSON Mode output."""

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
        """Invoke Gemini generateContent API with responseMimeType='application/json'."""
        if not self._settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY is not set; using ContextGroundedLocalLLMProvider."
            )
            return await self._fallback.generate_mind_map_json(
                system_prompt, user_prompt, query, context_chunks
            )

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._settings.gemini_model}:generateContent?key={self._settings.gemini_api_key}"
        )
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": self._settings.llm_temperature,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class OllamaLLMProvider(BaseLLMProvider):
    """Local open-source LLM provider via Ollama configured for strict JSON mode."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Invoke local Ollama /api/chat endpoint with format='json'."""
        url = f"{self._settings.ollama_base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self._settings.ollama_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": self._settings.llm_temperature},
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    """Factory returning the configured LLM provider instance (Gemini, Ollama, or Local)."""
    active_settings = settings or get_settings()
    provider_name = active_settings.llm_provider.strip().lower()

    if provider_name == "gemini":
        return GeminiLLMProvider(settings=active_settings)
    if provider_name == "ollama":
        return OllamaLLMProvider(settings=active_settings)
    return ContextGroundedLocalLLMProvider()

