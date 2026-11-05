from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.health import HealthResponse
from app.services.ollama_readiness import OllamaReadiness, check_ollama_readiness

ReadinessChecker = Callable[[Settings], Awaitable[OllamaReadiness]]


class HealthCheckUseCase:
    """Use case verifying vector database and Ollama readiness."""

    def __init__(
        self,
        repository: DocumentRepository,
        settings: Settings,
        readiness_checker: ReadinessChecker = check_ollama_readiness,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._readiness_checker = readiness_checker

    async def execute(self) -> HealthResponse:
        """Execute health verification and return contract."""
        db_connected = await self._repository.check_connection()
        readiness = await self._readiness_checker(self._settings)

        issues = list(readiness.issues)
        if not db_connected:
            issues.insert(0, "Database or pgvector extension is not available.")

        return HealthResponse(
            status="healthy" if not issues else "degraded",
            service=self._settings.app_name,
            environment=self._settings.app_env,
            database_connected=db_connected,
            ollama_connected=readiness.reachable,
            missing_models=readiness.missing_models,
            embedding_dimension=readiness.embedding_dimension,
            issues=issues,
        )
