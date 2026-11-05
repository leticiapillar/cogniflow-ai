from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.repositories.models import DocumentModel
from app.routers.dependencies import provide_embedding_provider
from app.services.chunking import chunk_pages
from app.services.pdf_parser import PdfPage, parse_pdf
from tests.fakes.embeddings import FailingEmbeddingProvider

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHOTOSYNTHESIS_PDF = PROJECT_ROOT / "fotossintese-texto-selecionavel.pdf"


def upload(name: str) -> dict[str, tuple[str, bytes, str]]:
    return {"file": (name, PHOTOSYNTHESIS_PDF.read_bytes(), "application/pdf")}


def test_chunks_keep_section_titles_and_page_ranges() -> None:
    pages = [
        PdfPage(number=1, text="# Fotossíntese\n" + "A planta produz glicose. " * 30),
        PdfPage(number=3, text="Continuação na página três.\n\n## Fatores\nLuz e CO2."),
    ]
    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=50)

    assert chunks[0].section_title == "Fotossíntese"
    assert chunks[0].page_start == 1
    continuation = next(c for c in chunks if "Continuação" in c.content)
    assert continuation.section_title == "Fotossíntese"
    assert (continuation.page_start, continuation.page_end) == (3, 3)
    assert chunks[-1].section_title == "Fatores"
    assert (chunks[-1].page_start, chunks[-1].page_end) == (3, 3)
    assert all(c.page_start <= c.page_end for c in chunks)


def test_real_pdf_chunks_map_to_existing_pages() -> None:
    parsed = parse_pdf(PHOTOSYNTHESIS_PDF.read_bytes())
    chunks = chunk_pages(parsed.pages)

    assert chunks
    assert all(1 <= c.page_start <= c.page_end <= parsed.page_count for c in chunks)
    covered = {p for c in chunks for p in range(c.page_start, c.page_end + 1)}
    assert covered == {page.number for page in parsed.pages}
    bibliography = next(c for c in chunks if c.section_title == "BIBLIOGRAFIA")
    assert (bibliography.page_start, bibliography.page_end) == (2, 3)


async def test_ingestion_returns_503_when_embedding_provider_fails(
    async_client: AsyncClient,
) -> None:
    app.dependency_overrides[provide_embedding_provider] = FailingEmbeddingProvider
    response = await async_client.post(
        "/api/documents/ingest", files=upload("falha-embedding.pdf")
    )

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]
    chunks = await async_client.get("/api/documents/falha-embedding.pdf/chunks")
    assert chunks.json() == []


async def test_failed_reingestion_keeps_previous_version(
    async_client: AsyncClient,
) -> None:
    name = "fotossintese-reingestao.pdf"
    first = await async_client.post("/api/documents/ingest", files=upload(name))
    assert first.status_code == 201

    app.dependency_overrides[provide_embedding_provider] = FailingEmbeddingProvider
    second = await async_client.post("/api/documents/ingest", files=upload(name))
    assert second.status_code == 503

    chunks = await async_client.get(f"/api/documents/{name}/chunks")
    assert len(chunks.json()) == first.json()["total_chunks"]


async def test_generate_map_refuses_document_from_another_embedding_model(
    async_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    name = "fotossintese-modelo-antigo.pdf"
    ingest = await async_client.post("/api/documents/ingest", files=upload(name))
    assert ingest.status_code == 201

    await db_session.execute(
        update(DocumentModel)
        .where(DocumentModel.name == name)
        .values(embedding_model="nomic-embed-text")
    )
    await db_session.commit()

    response = await async_client.post(
        "/api/generate-map",
        json={"query": "O que é fotossíntese?", "document_name": name, "top_k": 3},
    )
    assert response.status_code == 409
    assert "Upload the PDF again" in response.json()["detail"]
