"""LLM test doubles. They exercise the pipeline wiring, never pedagogical quality."""

from collections.abc import Callable, Sequence
import json
import math
import re
from typing import Any

from app.services.llm_provider import BaseLLMProvider, LLMProviderError

CHUNK_LINE = re.compile(r"^\[Trecho (\d+)\] (.+)$", re.MULTILINE)
CONCEPT_LINE = re.compile(r"^- (c\d+) \| ([^|]+) \|", re.MULTILINE)
SELECTION_LIMIT = re.compile(r"no máximo (\d+) conceitos")


CURRENT_QUESTION = re.compile(r"^Pergunta atual: (.+)$", re.MULTILINE)


def task_of(json_schema: dict[str, Any]) -> str:
    properties = json_schema.get("properties", {})
    if "found_in_material" in properties:
        return "answer"
    if "question" in properties:
        return "rewrite"
    if "axes" in properties:
        return "organization"
    if "concept_ids" in properties:
        return "selection"
    return "extraction"


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic answers derived from the prompt itself (one concept per chunk)."""

    def __init__(self, model_name: str = "fake-llm") -> None:
        self.model_name = model_name
        self.calls: list[tuple[str, str]] = []

    async def generate_json(
        self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> str:
        task = task_of(json_schema)
        self.calls.append((task, user_prompt))
        return json.dumps(getattr(self, f"_{task}")(user_prompt), ensure_ascii=False)

    def _extraction(self, prompt: str) -> dict[str, Any]:
        concepts = []
        for index, text in CHUNK_LINE.findall(prompt)[:8]:
            words = re.findall(r"[A-Za-zÀ-ÿ0-9]{3,}", text)
            if not words:
                continue
            concepts.append(
                {
                    "label": " ".join(words[:3]),
                    "summary": text[:200],
                    "acronyms": [],
                    "examples": [],
                    "source_chunks": [int(index)],
                }
            )
        return {"concepts": concepts}

    def _selection(self, prompt: str) -> dict[str, Any]:
        limit = int(SELECTION_LIMIT.search(prompt).group(1))  # type: ignore[union-attr]
        return {"concept_ids": [cid for cid, _ in CONCEPT_LINE.findall(prompt)][:limit]}

    def _organization(self, prompt: str) -> dict[str, Any]:
        ids = [cid for cid, _ in CONCEPT_LINE.findall(prompt)]
        axis_count = min(5, max(min(3, len(ids)), math.ceil(len(ids) / 5)))
        bounds = [round(i * len(ids) / axis_count) for i in range(axis_count + 1)]
        axes = [
            {
                "title": f"Parte {number}",
                "summary": f"Conceitos da parte {number} do material.",
                "concepts": [
                    {"id": cid, "relation": "has_part"}
                    for cid in ids[bounds[number - 1] : bounds[number]]
                ],
            }
            for number in range(1, axis_count + 1)
        ]
        return {
            "topic": "Tema da aula",
            "synthesis": "A aula apresenta o tema central. O tema é importante para a disciplina.",
            "axes": axes,
        }


    def _rewrite(self, prompt: str) -> dict[str, Any]:
        current = CURRENT_QUESTION.search(prompt).group(1)  # type: ignore[union-attr]
        return {"question": f"Pergunta completa: {current}"}

    def _answer(self, prompt: str) -> dict[str, Any]:
        cited = [int(index) for index, _ in CHUNK_LINE.findall(prompt)][:1]
        return {
            "found_in_material": True,
            "answer": f"A resposta está no trecho {cited[0]}.",
            "key_points": ["Primeiro ponto.", "Segundo ponto.", "Terceiro ponto.", "Quarto ponto."],
            "example": "",
            "terms": [{"term": "Fotossíntese", "definition": "Processo das plantas."}],
            "citations": cited,
        }


class ScriptedLLMProvider(BaseLLMProvider):
    """Returns pre-defined answers in order; exceptions in the script are raised."""

    def __init__(self, answers: Sequence[str | Exception], model_name: str = "fake-llm") -> None:
        self.model_name = model_name
        self._answers = list(answers)
        self.prompts: list[str] = []

    async def generate_json(
        self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> str:
        self.prompts.append(user_prompt)
        answer = self._answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class SelectiveFailureLLMProvider(FakeLLMProvider):
    """Like FakeLLMProvider, but answers invalid JSON when `should_fail(task, prompt)`."""

    def __init__(self, should_fail: Callable[[str, str], bool]) -> None:
        super().__init__()
        self._should_fail = should_fail

    async def generate_json(
        self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> str:
        if self._should_fail(task_of(json_schema), user_prompt):
            self.calls.append((task_of(json_schema), user_prompt))
            return "this is not json"
        return await super().generate_json(system_prompt, user_prompt, json_schema)


class UnavailableLLMProvider(FakeLLMProvider):
    """Behaves like an Ollama server that is down."""

    async def generate_json(
        self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> str:
        raise LLMProviderError("Ollama LLM 'fake-llm' is unavailable after 3 attempts.")
