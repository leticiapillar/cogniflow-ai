from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response contract."""

    status: str = Field(
        ...,
        examples=["healthy"],
        description="'healthy' when every dependency is ready, otherwise 'degraded'.",
    )
    service: str = Field(
        ..., examples=["CogniFlow AI Backend"], description="Application name."
    )
    environment: str = Field(
        ..., examples=["development"], description="Current runtime environment."
    )
    database_connected: bool = Field(
        default=True, description="Indicates whether database connectivity is active."
    )
    ollama_connected: bool = Field(
        default=False, description="Indicates whether the Ollama server is reachable."
    )
    missing_models: list[str] = Field(
        default_factory=list,
        description="Configured Ollama models that are not installed on the server.",
    )
    embedding_dimension: int | None = Field(
        default=None,
        description="Vector dimension returned by the configured embedding model.",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Reasons why the service is degraded (empty when healthy).",
    )
