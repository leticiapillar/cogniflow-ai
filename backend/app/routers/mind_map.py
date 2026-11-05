from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.routers.dependencies import provide_embedding_provider, provide_llm_provider
from app.schemas.mind_map import GenerateMapRequest, GenerateMapResponse
from app.services.embeddings import BaseEmbeddingProvider, EmbeddingProviderError
from app.services.llm_provider import BaseLLMProvider
from app.services.output_validator import LLMOutputValidationError
from app.use_cases.errors import EmbeddingModelMismatchError
from app.use_cases.generate_mind_map import GenerateMindMapUseCase

router = APIRouter(prefix="/api", tags=["Mind Map"])


def get_generate_mind_map_use_case(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    embedding_provider: BaseEmbeddingProvider = Depends(provide_embedding_provider),
    llm_provider: BaseLLMProvider = Depends(provide_llm_provider),
) -> GenerateMindMapUseCase:
    """Dependency provider for GenerateMindMapUseCase."""
    repository = DocumentRepository(session=session)
    return GenerateMindMapUseCase(
        repository=repository,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider,
        settings=settings,
    )


@router.post("/generate-map", response_model=GenerateMapResponse, status_code=200)
async def generate_mind_map(
    request: GenerateMapRequest,
    use_case: GenerateMindMapUseCase = Depends(get_generate_mind_map_use_case),
) -> GenerateMapResponse:
    """Generate a structured mind map (nodes and edges) for React Flow using RAG + LLM."""
    try:
        return await use_case.execute(request=request)
    except EmbeddingModelMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMOutputValidationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
