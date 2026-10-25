from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.schemas.health import HealthResponse
from app.use_cases.health_check import HealthCheckUseCase

router = APIRouter(prefix="/api", tags=["Health"])


def get_health_use_case(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> HealthCheckUseCase:
    """Dependency provider for HealthCheckUseCase."""
    repository = DocumentRepository(session=session)
    return HealthCheckUseCase(repository=repository, settings=settings)


@router.get("/health", response_model=HealthResponse, status_code=200)
async def check_health(
    use_case: HealthCheckUseCase = Depends(get_health_use_case),
) -> HealthResponse:
    """Return service and database health status."""
    return await use_case.execute()

