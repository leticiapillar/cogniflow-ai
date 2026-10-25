from app.core.config import Settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.health import HealthResponse


class HealthCheckUseCase:
    """Use case verifying service and vector database health."""

    def __init__(
        self, repository: DocumentRepository, settings: Settings
    ) -> None:
        self._repository = repository
        self._settings = settings

    async def execute(self) -> HealthResponse:
        """Execute health verification and return contract."""
        db_connected = await self._repository.check_connection()
        status = "healthy" if db_connected else "degraded"
        return HealthResponse(
            status=status,
            service=self._settings.app_name,
            environment=self._settings.app_env,
            database_connected=db_connected,
        )

