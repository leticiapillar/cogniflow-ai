from dataclasses import dataclass, field
import time
from typing import Any

from app.services.llm_provider import BaseLLMProvider

CORRECTION_MARKER = "ATENÇÃO: a sua resposta anterior tinha estes problemas"


def task_of(json_schema: dict[str, Any]) -> str:
    properties = json_schema.get("properties", {})
    for key, task in (
        ("found_in_material", "tutor_answer"),
        ("question", "rewrite_question"),
        ("axes", "organization"),
        ("concept_ids", "selection"),
        ("concepts", "map_section"),
    ):
        if key in properties:
            return task
    return "unknown"


@dataclass
class LLMCall:
    task: str
    is_correction: bool
    seconds: float


@dataclass
class RecordingLLMProvider(BaseLLMProvider):
    """Wraps the real provider and records every call (task, correction, latency)."""

    inner: BaseLLMProvider
    calls: list[LLMCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.model_name = self.inner.model_name

    async def generate_json(self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]) -> str:
        start = time.perf_counter()
        try:
            return await self.inner.generate_json(system_prompt, user_prompt, json_schema)
        finally:
            self.calls.append(
                LLMCall(
                    task=task_of(json_schema),
                    is_correction=CORRECTION_MARKER in user_prompt,
                    seconds=time.perf_counter() - start,
                )
            )

    def requests(self, task: str | None = None) -> list[list[LLMCall]]:
        """Group calls into structured requests: the first call plus its corrections."""
        grouped: list[list[LLMCall]] = []
        for call in self.calls:
            if task and call.task != task:
                continue
            if call.is_correction and grouped:
                grouped[-1].append(call)
            else:
                grouped.append([call])
        return grouped

    def first_attempt_rate(self, task: str | None = None) -> float | None:
        """Share of requests answered with valid output at the first attempt."""
        requests = self.requests(task)
        if not requests:
            return None
        return sum(1 for request in requests if len(request) == 1) / len(requests)
