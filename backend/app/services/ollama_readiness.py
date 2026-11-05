from dataclasses import dataclass, field
import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger("cogniflow.services.ollama_readiness")

TAGS_TIMEOUT_SECONDS = 5.0
# The first embedding request loads the model into memory, which can take a while.
EMBED_PROBE_TIMEOUT_SECONDS = 60.0
EMBED_PROBE_TEXT = "verificação de prontidão"

# A model's output dimension never changes, so a successful probe is cached per server/model.
_probed_dimensions: dict[tuple[str, str], int] = {}


@dataclass
class OllamaReadiness:
    """Outcome of verifying that the Ollama server is ready to serve this application."""

    reachable: bool = False
    missing_models: list[str] = field(default_factory=list)
    embedding_dimension: int | None = None
    issues: list[str] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return not self.issues


def _normalize_model_name(name: str) -> str:
    """Ollama lists untagged models with the implicit ':latest' tag."""
    name = name.strip()
    return name if ":" in name else f"{name}:latest"


def clear_dimension_cache() -> None:
    """Forget cached embedding dimensions (used by tests)."""
    _probed_dimensions.clear()


async def check_ollama_readiness(
    settings: Settings,
    client: httpx.AsyncClient | None = None,
) -> OllamaReadiness:
    """Check server reachability, required models, and the embedding dimension."""
    result = OllamaReadiness()
    base_url = settings.ollama_base_url.rstrip("/")
    required_models = [settings.ollama_embedding_model, settings.ollama_llm_model]

    owns_client = client is None
    http = client or httpx.AsyncClient()
    try:
        try:
            response = await http.get(f"{base_url}/api/tags", timeout=TAGS_TIMEOUT_SECONDS)
            response.raise_for_status()
            installed = {
                _normalize_model_name(str(item.get("name", "")))
                for item in response.json().get("models", [])
            }
        except Exception as exc:
            result.issues.append(f"Ollama server is unreachable at {base_url}: {exc}")
            return result

        result.reachable = True
        result.missing_models = [
            model for model in required_models
            if _normalize_model_name(model) not in installed
        ]
        if result.missing_models:
            result.issues.append(
                "Required Ollama models are not installed: "
                + ", ".join(result.missing_models)
            )

        embedding_model = settings.ollama_embedding_model
        if embedding_model in result.missing_models:
            return result

        cache_key = (base_url, embedding_model)
        dimension = _probed_dimensions.get(cache_key)
        if dimension is None:
            try:
                response = await http.post(
                    f"{base_url}/api/embed",
                    json={"model": embedding_model, "input": EMBED_PROBE_TEXT},
                    timeout=EMBED_PROBE_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                dimension = len(response.json()["embeddings"][0])
            except Exception as exc:
                result.issues.append(
                    f"Embedding probe with model '{embedding_model}' failed: {exc}"
                )
                return result
            _probed_dimensions[cache_key] = dimension

        result.embedding_dimension = dimension
        if dimension != settings.embedding_dimension:
            result.issues.append(
                f"Embedding model '{embedding_model}' returns {dimension} dimensions, "
                f"but EMBEDDING_DIMENSION={settings.embedding_dimension}."
            )
        return result
    finally:
        if owns_client:
            await http.aclose()
