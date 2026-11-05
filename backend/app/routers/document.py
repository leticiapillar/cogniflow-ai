from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.routers.dependencies import provide_embedding_provider
from app.routers.mind_map import get_mind_map_use_case
from app.schemas.document import DocumentChunkSchema, DocumentUploadResponse
from app.services.embeddings import BaseEmbeddingProvider, EmbeddingProviderError
from app.services.pdf_parser import PDFParsingError
from app.services.sanitizer import InputValidationError, PromptInjectionError
from app.use_cases.ingest_document import IngestDocumentUseCase
from app.use_cases.mind_map_generation import MindMapGenerationUseCase

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def get_ingest_document_use_case(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    embedding_provider: BaseEmbeddingProvider = Depends(provide_embedding_provider),
) -> IngestDocumentUseCase:
    """Dependency provider for IngestDocumentUseCase."""
    repository = DocumentRepository(session=session)
    return IngestDocumentUseCase(
        repository=repository,
        embedding_provider=embedding_provider,
        settings=settings,
    )


@router.post("/ingest", response_model=DocumentUploadResponse, status_code=201)
async def ingest_pdf_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
    mind_map_use_case: MindMapGenerationUseCase = Depends(get_mind_map_use_case),
) -> DocumentUploadResponse:
    """Store a PDF's chunks and vectors, then generate its mind map in the background.

    Follow the generation with GET /api/documents/{document_id}/mind-map.
    """
    try:
        file_bytes = await file.read()
        response = await use_case.execute_pdf_upload(
            filename=file.filename or "",
            content_type=file.content_type,
            file_bytes=file_bytes,
        )
    except PromptInjectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InputValidationError, PDFParsingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if await mind_map_use_case.request_generation(response.document_id):
        background_tasks.add_task(mind_map_use_case.run, response.document_id)
    return response


@router.get(
    "/{document_name}/chunks",
    response_model=list[DocumentChunkSchema],
    status_code=200,
)
async def get_document_chunks(
    document_name: str,
    use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
) -> list[DocumentChunkSchema]:
    """Retrieve all stored chunks for a specific document."""
    return await use_case.list_document_chunks(document_name=document_name)
