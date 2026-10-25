from functools import lru_cache
from typing import Any, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    embedding_provider: str = Field(default="local", alias="EMBEDDING_PROVIDER")
    llm_provider: str = Field(default="local", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")

    gemini_api_key: Optional[str] = Field(
        default=None, alias="GEMINI_API_KEY", repr=False
    )
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    ollama_base_url: str = Field(
        default="http://localhost:11434", alias="OLLAMA_BASE_URL"
    )
    ollama_embedding_model: str = Field(
        default="nomic-embed-text", alias="OLLAMA_EMBEDDING_MODEL"
    )
    ollama_llm_model: str = Field(default="llama3.2", alias="OLLAMA_LLM_MODEL")

    model_config = SettingsConfigDict(
        env_file=".env",
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
