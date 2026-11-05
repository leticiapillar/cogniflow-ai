import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_session_factory
from app.routers.dependencies import provide_embedding_provider, provide_llm_provider
from app.schemas.mind_map import MindMapStatusResponse
from app.services.embeddings import BaseEmbeddingProvider
from app.services.llm_provider import BaseLLMProvider
from app.use_cases.errors import (
    DocumentNotFoundError,
    GenerationInProgressError,
    MindMapNotFoundError,
    SectionNotRetryableError,
)
from app.use_cases.mind_map_generation import MindMapGenerationUseCase

router = APIRouter(prefix="/api", tags=["Mind Map"])

RETIRED_GENERATE_MAP_DETAIL = (
    "POST /api/generate-map was retired: the mind map now covers the whole document and is "
    "generated after ingestion. Use GET /api/documents/{document_id}/mind-map."
)


def get_mind_map_use_case(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    embedding_provider: BaseEmbeddingProvider = Depends(provide_embedding_provider),
    llm_provider: BaseLLMProvider = Depends(provide_llm_provider),
) -> MindMapGenerationUseCase:
    """Dependency provider for MindMapGenerationUseCase."""
    return MindMapGenerationUseCase(
        session_factory=session_factory,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
    )


@router.get(
    "/documents/{document_id}/mind-map",
    response_model=MindMapStatusResponse,
    status_code=200,
)
async def get_mind_map(
    document_id: uuid.UUID,
    use_case: MindMapGenerationUseCase = Depends(get_mind_map_use_case),
) -> MindMapStatusResponse:
    """Return the generation status, progress and (when available) the mind map."""
    try:
        return await use_case.get_status(document_id)
    except (DocumentNotFoundError, MindMapNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/documents/{document_id}/mind-map/regenerate",
    response_model=MindMapStatusResponse,
    status_code=202,
)
async def regenerate_mind_map(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    use_case: MindMapGenerationUseCase = Depends(get_mind_map_use_case),
) -> MindMapStatusResponse:
    """Discard the current map and generate it again in the background."""
    try:
        await use_case.request_generation(document_id, force=True)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GenerationInProgressError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(use_case.run, document_id)
    return await use_case.get_status(document_id)


@router.post(
    "/documents/{document_id}/mind-map/sections/{section_index}/retry",
    response_model=MindMapStatusResponse,
    status_code=202,
)
async def retry_mind_map_section(
    document_id: uuid.UUID,
    section_index: int,
    background_tasks: BackgroundTasks,
    use_case: MindMapGenerationUseCase = Depends(get_mind_map_use_case),
) -> MindMapStatusResponse:
    """Reprocess only a section that failed, then rebuild the map."""
    try:
        await use_case.request_section_retry(document_id, section_index)
    except MindMapNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (GenerationInProgressError, SectionNotRetryableError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(use_case.run_section_retry, document_id, section_index)
    return await use_case.get_status(document_id)


@router.post("/generate-map", status_code=410, include_in_schema=False)
async def generate_map_retired() -> None:
    """Retired endpoint kept for one version to guide old clients."""
    raise HTTPException(status_code=410, detail=RETIRED_GENERATE_MAP_DETAIL)
