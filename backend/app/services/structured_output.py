from collections.abc import Callable
import logging
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.services.llm_provider import BaseLLMProvider

logger = logging.getLogger("cogniflow.services.structured_output")

T = TypeVar("T", bound=BaseModel)

# Returns the (possibly normalized) output and the problems to report back to the model.
SemanticValidator = Callable[[T], tuple[T, list[str]]]

MAX_CORRECTIONS = 2


class StructuredOutputError(RuntimeError):
    """Raised when the model keeps answering with invalid output after the corrections."""


def inline_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema of a Pydantic model with `$ref`s inlined (simpler for Ollama's grammar)."""
    schema = model.model_json_schema()
    definitions = schema.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(definitions[node["$ref"].split("/")[-1]])
            return {key: resolve(value) for key, value in node.items() if key != "title"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    return resolve(schema)


def _format_validation_error(exc: ValidationError) -> list[str]:
    problems = []
    for error in exc.errors()[:6]:
        location = ".".join(str(part) for part in error["loc"]) or "resposta"
        problems.append(f"{location}: {error['msg']}")
    return problems


def _correction_prompt(user_prompt: str, problems: list[str]) -> str:
    listed = "\n".join(f"- {problem}" for problem in problems)
    return (
        f"{user_prompt}\n\n"
        "ATENÇÃO: a sua resposta anterior tinha estes problemas:\n"
        f"{listed}\n"
        "Corrija todos os problemas e responda novamente apenas com o JSON."
    )


async def generate_structured(
    llm: BaseLLMProvider,
    system_prompt: str,
    user_prompt: str,
    output_model: type[T],
    validate: SemanticValidator[T] | None = None,
    max_corrections: int = MAX_CORRECTIONS,
) -> T:
    """Ask for JSON in `output_model`'s shape; on invalid output, retry citing the errors.

    LLMProviderError (provider unavailable) is not caught: it propagates to the caller.
    """
    schema = inline_json_schema(output_model)
    prompt = user_prompt
    problems: list[str] = []
    for attempt in range(max_corrections + 1):
        raw = await llm.generate_json(system_prompt, prompt, schema)
        try:
            parsed = output_model.model_validate_json(raw)
        except ValidationError as exc:
            problems = _format_validation_error(exc)
        else:
            if validate is None:
                return parsed
            parsed, problems = validate(parsed)
            if not problems:
                return parsed

        logger.warning(
            "%s attempt %d/%d invalid: %s",
            output_model.__name__,
            attempt + 1,
            max_corrections + 1,
            "; ".join(problems),
        )
        prompt = _correction_prompt(user_prompt, problems)

    raise StructuredOutputError(
        f"Invalid {output_model.__name__} after {max_corrections + 1} attempts: "
        + "; ".join(problems)
    )
