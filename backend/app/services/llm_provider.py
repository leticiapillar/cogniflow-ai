from abc import ABC, abstractmethod
import json
import logging
import re
from typing import Sequence

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("cogniflow.services.llm_provider")

GEMINI_MIND_MAP_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "required": ["topic", "nodes", "edges"],
    "properties": {
        "topic": {"type": "STRING"},
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
    """Deterministic, context-grounded JSON generator extracting concepts directly from RAG chunks."""

    async def generate_mind_map_json(
        self,
        system_prompt: str,
        user_prompt: str,
        query: str,
        context_chunks: Sequence[str],
    ) -> str:
        """Extract key concepts and summaries from retrieved chunks into strict hierarchical JSON."""
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
        if len(extracted_items) >= 4:
            # Group extracted items into 2-level hierarchy (root -> topic pillar -> concepts)
            pillar_size = 2 if len(extracted_items) <= 5 else 3
            concept_counter = 1
            for group_idx, start in enumerate(
                range(0, len(extracted_items), pillar_size), start=1
            ):
                group = extracted_items[start : start + pillar_size]
                if not group:
                    continue
                pillar_label, pillar_summary = group[0]
                topic_id = f"node-topic-{group_idx}"
                nodes.append(
                    {
                        "id": topic_id,
                        "type": "default",
                        "data": {
                            "label": pillar_label[:180],
                            "summary": pillar_summary[:800],
                            "category": "topic",
                        },
                        "position": {"x": float((group_idx - 1) * 280), "y": 140.0},
                    }
                )
                edges.append(
                    {
                        "id": f"edge-root-topic-{group_idx}",
                        "source": root_id,
                        "target": topic_id,
                        "label": "structures into",
                        "animated": False,
                    }
                )
                for child_label, child_summary in group[1:]:
                    concept_id = f"node-{concept_counter}"
                    concept_counter += 1
                    nodes.append(
                        {
                            "id": concept_id,
                            "type": "default",
                            "data": {
                                "label": child_label[:180],
                                "summary": child_summary[:800],
                                "category": "concept",
                            },
                            "position": {
                                "x": float((group_idx - 1) * 280),
                                "y": 280.0,
                            },
                        }
                    )
                    edges.append(
                        {
                            "id": f"edge-topic-{group_idx}-concept-{concept_counter - 1}",
                            "source": topic_id,
                            "target": concept_id,
                            "label": "encompasses",
                            "animated": False,
                        }
                    )
        else:
            for index, (label, summary) in enumerate(extracted_items, start=1):
                node_id = f"node-{index}"
                nodes.append(
                    {
                        "id": node_id,
                        "type": "default",
                        "data": {
                            "label": label[:180],
                            "summary": summary[:800],
                            "category": "topic" if index == 1 else "concept",
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

    FALLBACK_MODELS: tuple[str, ...] = (
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-flash-latest",
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
                    if response.status_code in {429, 500, 502, 503, 504}:
                        logger.warning(
                            "Gemini model '%s' returned HTTP %d; trying next candidate model.",
                            model_name,
                            response.status_code,
                        )
                        response.raise_for_status()
                    response.raise_for_status()
                    data = response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
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
                "num_ctx": 4096,
                "num_predict": 900,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=110.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]
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

