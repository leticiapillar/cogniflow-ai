from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentChunkSchema, DocumentUploadResponse
from app.services.pdf_parser import PDFParsingError
from app.services.sanitizer import InputValidationError, PromptInjectionError
from app.use_cases.ingest_document import IngestDocumentUseCase

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def get_ingest_document_use_case(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> IngestDocumentUseCase:
    """Dependency provider for IngestDocumentUseCase."""
    repository = DocumentRepository(session=session)
    return IngestDocumentUseCase(repository=repository, settings=settings)


@router.post("/ingest", response_model=DocumentUploadResponse, status_code=201)
async def ingest_pdf_document(
    file: UploadFile = File(...),
    use_case: IngestDocumentUseCase = Depends(get_ingest_document_use_case),
) -> DocumentUploadResponse:
    """Upload a PDF document, sanitize content, chunk semantically, and store embeddings in pgvector."""
    try:
        file_bytes = await file.read()
        return await use_case.execute_pdf_upload(
            filename=file.filename or "",
            content_type=file.content_type,
            file_bytes=file_bytes,
        )
    except PromptInjectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (InputValidationError, PDFParsingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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

