from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = BACKEND_DIR / ".env"

SUPPORTED_PROVIDERS = frozenset({"ollama"})

SENSITIVE_FIELD_NAMES = frozenset(
    {
        "postgres_password",
        "database_url_override",
        "gemini_api_key",
    }
)


class Settings(BaseSettings):
    """Application settings loaded from environment variables with secret masking."""

    app_name: str = Field(default="CogniFlow AI Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    postgres_user: str = Field(default="cogniflow", alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="cogniflow_secret", alias="POSTGRES_PASSWORD", repr=False
    )
    postgres_db: str = Field(default="cogniflow_db", alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    database_url_override: Optional[str] = Field(
        default=None, alias="DATABASE_URL", repr=False
    )

    cors_origins: List[str] = Field(
        default=["http://localhost:3000"], alias="CORS_ORIGINS"
    )

    chunk_size: int = Field(default=800, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=150, alias="CHUNK_OVERLAP")
    max_pdf_size_bytes: int = Field(
        default=20 * 1024 * 1024, alias="MAX_PDF_SIZE_BYTES"
    )

    embedding_provider: str = Field(default="ollama", alias="EMBEDDING_PROVIDER")
    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    embedding_dimension: int = Field(default=1024, gt=0, alias="EMBEDDING_DIMENSION")

    # Gemini is not supported in this version; settings are kept so the provider
    # can be reintroduced later without changing the configuration contract.
    gemini_api_key: Optional[str] = Field(
        default=None, alias="GEMINI_API_KEY", repr=False
    )
    gemini_model: str = Field(default="gemini-flash-latest", alias="GEMINI_MODEL")
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001", alias="GEMINI_EMBEDDING_MODEL"
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_embedding_model: str = Field(
        default="bge-m3", alias="OLLAMA_EMBEDDING_MODEL"
    )
    ollama_llm_model: str = Field(default="llama3.2:3b", alias="OLLAMA_LLM_MODEL")
    ollama_num_ctx: int = Field(default=8192, gt=0, alias="OLLAMA_NUM_CTX")

    @field_validator("embedding_provider", "llm_provider", mode="before")
    @classmethod
    def validate_supported_provider(cls, value: object, info: ValidationInfo) -> str:
        """Accept only providers supported in this version; fail fast on anything else."""
        normalized = str(value).strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
            raise ValueError(
                f"Unsupported {info.field_name} '{value}'. Supported providers: {supported}."
            )
        return normalized

    model_config = SettingsConfigDict(
        env_file=(ENV_FILE_PATH, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def database_url(self) -> str:
        """Build the asynchronous SQLAlchemy database URL."""
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def get_safe_config_summary(self) -> dict[str, Any]:
        """Return a dictionary of settings with all sensitive values redacted."""
        raw = self.model_dump()
        for key in SENSITIVE_FIELD_NAMES:
            if key in raw and raw[key] is not None:
                raw[key] = "***REDACTED***"
        return raw


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()
