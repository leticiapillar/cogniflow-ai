import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.routers.dependencies import provide_embedding_provider, provide_llm_provider
from app.schemas.tutor import AskRequest, AskResponse
from app.services.embeddings import BaseEmbeddingProvider, EmbeddingProviderError
from app.services.llm_provider import BaseLLMProvider
from app.use_cases.ask_tutor import AskTutorUseCase, MindMapNodeNotFoundError, TutorUnavailableError
from app.use_cases.errors import DocumentNotFoundError, EmbeddingModelMismatchError

router = APIRouter(prefix="/api/documents", tags=["Tutor"])

TUTOR_UNAVAILABLE_DETAIL = "O tutor está indisponível no momento. Tente novamente em instantes."


def get_ask_tutor_use_case(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    embedding_provider: BaseEmbeddingProvider = Depends(provide_embedding_provider),
    llm_provider: BaseLLMProvider = Depends(provide_llm_provider),
) -> AskTutorUseCase:
    """Dependency provider for AskTutorUseCase."""
    return AskTutorUseCase(
        session=session,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        top_k=settings.tutor_top_k,
        min_similarity=settings.tutor_min_similarity,
    )


@router.post("/{document_id}/ask", response_model=AskResponse, status_code=200)
async def ask_tutor(
    document_id: uuid.UUID,
    request: AskRequest,
    use_case: AskTutorUseCase = Depends(get_ask_tutor_use_case),
) -> AskResponse:
    """Answer a student's question using only the class material (RAG), citing its pages."""
    try:
        return await use_case.ask(document_id, request)
    except (DocumentNotFoundError, MindMapNodeNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EmbeddingModelMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (TutorUnavailableError, EmbeddingProviderError) as exc:
        raise HTTPException(status_code=503, detail=TUTOR_UNAVAILABLE_DETAIL) from exc
