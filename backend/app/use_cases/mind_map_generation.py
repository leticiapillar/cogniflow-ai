from collections.abc import Sequence
import logging
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.models import DocumentChunkModel, DocumentModel, MindMapModel
from app.schemas.mind_map import (
    FailedSection,
    MindMapGraph,
    MindMapProgress,
    MindMapStatusResponse,
)
from app.services.embeddings import BaseEmbeddingProvider, EmbeddingProviderError
from app.services.llm_provider import BaseLLMProvider, LLMProviderError
from app.services.mind_map.llm_schemas import ExtractedConcept
from app.services.mind_map.pipeline import MindMapGenerationError, MindMapPipeline
from app.services.mind_map.units import MapUnit, build_map_units
from app.services.structured_output import StructuredOutputError
from app.use_cases.errors import (
    DocumentNotFoundError,
    GenerationInProgressError,
    MindMapNotFoundError,
    SectionNotRetryableError,
)

logger = logging.getLogger("cogniflow.use_cases.mind_map_generation")

ACTIVE_STATUSES = ("pending", "processing")
INTERRUPTED_ERROR = "The generation was interrupted by a server restart. Generate the map again."


def progress_message(status: str, phase: str, done: int, total: int, current: str | None) -> str:
    """Literal, predictable progress text in Portuguese."""
    if status == "pending":
        return "Aguardando o início da geração do mapa."
    if status == "ready":
        return "Mapa pronto."
    if status == "partial":
        return "Mapa pronto. Algumas seções não puderam ser processadas."
    if status == "failed":
        return "Não foi possível gerar o mapa."
    if phase == "consolidating":
        return "Juntando conceitos repetidos."
    if phase == "organizing":
        return "Organizando os eixos de estudo."
    position = min(done + 1, total) if total else 0
    suffix = f": {current}." if current else "."
    return f"Lendo a seção {position} de {total}{suffix}"


def _fallback_topic(document: DocumentModel, chunks: Sequence[DocumentChunkModel]) -> str:
    first_title = next((c.section_title for c in chunks if c.section_title), None)
    return (first_title or Path(document.name).stem.replace("_", " ").replace("-", " "))[:200]


class MindMapGenerationUseCase:
    """Generates, persists, and reports the map-reduce mind map of a document."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        llm_provider: BaseLLMProvider,
        embedding_provider: BaseEmbeddingProvider,
    ) -> None:
        self._session_factory = session_factory
        self._llm = llm_provider
        self._pipeline = MindMapPipeline(llm=llm_provider, embedder=embedding_provider)

    # ---- Persistence helpers -------------------------------------------------------------

    async def _load_map(self, session: AsyncSession, document_id: uuid.UUID) -> MindMapModel | None:
        result = await session.execute(
            select(MindMapModel).where(MindMapModel.document_id == document_id)
        )
        return result.scalar_one_or_none()

    async def _update(self, document_id: uuid.UUID, **fields: Any) -> None:
        async with self._session_factory() as session:
            mind_map = await self._load_map(session, document_id)
            if mind_map is None:
                return
            for name, value in fields.items():
                setattr(mind_map, name, value)
            await session.commit()

    async def _load_source(
        self, document_id: uuid.UUID
    ) -> tuple[DocumentModel, list[DocumentChunkModel]]:
        async with self._session_factory() as session:
            document = await session.get(DocumentModel, document_id)
            if document is None:
                raise DocumentNotFoundError(f"Document '{document_id}' not found.")
            result = await session.execute(
                select(DocumentChunkModel)
                .where(DocumentChunkModel.document_id == document_id)
                .order_by(DocumentChunkModel.chunk_index.asc())
            )
            return document, list(result.scalars().all())

    # ---- Queries -------------------------------------------------------------------------

    async def get_status(self, document_id: uuid.UUID) -> MindMapStatusResponse:
        async with self._session_factory() as session:
            document = await session.get(DocumentModel, document_id)
            if document is None:
                raise DocumentNotFoundError(f"Document '{document_id}' not found.")
            mind_map = await self._load_map(session, document_id)
            if mind_map is None:
                raise MindMapNotFoundError(
                    f"Document '{document.name}' has no mind map. Request a regeneration."
                )
            return MindMapStatusResponse(
                document_id=document.id,
                document_name=document.name,
                status=mind_map.status,  # type: ignore[arg-type]
                progress=MindMapProgress(
                    phase=mind_map.phase,  # type: ignore[arg-type]
                    done=mind_map.progress_done,
                    total=mind_map.progress_total,
                    current_section=mind_map.current_section,
                    message=progress_message(
                        mind_map.status,
                        mind_map.phase,
                        mind_map.progress_done,
                        mind_map.progress_total,
                        mind_map.current_section,
                    ),
                ),
                failed_sections=[FailedSection.model_validate(f) for f in mind_map.failed_sections],
                mind_map=(
                    MindMapGraph.model_validate(mind_map.payload) if mind_map.payload else None
                ),
                llm_model=mind_map.llm_model,
                error=mind_map.error,
                updated_at=mind_map.updated_at,
            )

    # ---- Commands ------------------------------------------------------------------------

    async def request_generation(self, document_id: uuid.UUID, force: bool = False) -> bool:
        """Put the map in 'pending'. Returns False when an up-to-date map can be reused.

        Raises GenerationInProgressError when forced while a generation is running.
        """
        async with self._session_factory() as session:
            if await session.get(DocumentModel, document_id) is None:
                raise DocumentNotFoundError(f"Document '{document_id}' not found.")
            mind_map = await self._load_map(session, document_id)
            if mind_map is not None:
                if mind_map.status in ACTIVE_STATUSES:
                    if force:
                        raise GenerationInProgressError(
                            "A mind map generation is already in progress for this document."
                        )
                    return False
                reusable = (
                    mind_map.status in ("ready", "partial")
                    and mind_map.llm_model == self._llm.model_name
                )
                if reusable and not force:
                    return False
            else:
                mind_map = MindMapModel(document_id=document_id, llm_model=self._llm.model_name)
                session.add(mind_map)

            mind_map.status = "pending"
            mind_map.phase = "pending"
            mind_map.progress_done = 0
            mind_map.progress_total = 0
            mind_map.current_section = None
            mind_map.section_results = {}
            mind_map.failed_sections = []
            mind_map.payload = None
            mind_map.error = None
            mind_map.llm_model = self._llm.model_name
            await session.commit()
            return True

    async def request_section_retry(self, document_id: uuid.UUID, section_index: int) -> None:
        """Validate and mark a failed section for reprocessing."""
        async with self._session_factory() as session:
            mind_map = await self._load_map(session, document_id)
            if mind_map is None:
                raise MindMapNotFoundError(f"Document '{document_id}' has no mind map.")
            if mind_map.status in ACTIVE_STATUSES:
                raise GenerationInProgressError(
                    "A mind map generation is already in progress for this document."
                )
            entry = mind_map.section_results.get(str(section_index))
            if entry is None or entry.get("status") != "failed":
                raise SectionNotRetryableError(
                    f"Section {section_index} did not fail; nothing to retry."
                )
            mind_map.status = "processing"
            mind_map.phase = "mapping"
            mind_map.progress_done = 0
            mind_map.progress_total = 1
            mind_map.current_section = entry.get("title")
            mind_map.error = None
            await session.commit()

    async def mark_interrupted(self) -> int:
        """On startup, fail generations left half-done by a previous process."""
        async with self._session_factory() as session:
            result = await session.execute(
                update(MindMapModel)
                .where(MindMapModel.status.in_(ACTIVE_STATUSES))
                .values(status="failed", phase="done", error=INTERRUPTED_ERROR)
            )
            await session.commit()
            return result.rowcount or 0

    # ---- Background work -----------------------------------------------------------------

    async def _map_unit(self, unit: MapUnit) -> dict[str, Any]:
        entry: dict[str, Any] = {"title": unit.title, "chunk_indices": unit.chunk_indices}
        try:
            concepts = await self._pipeline.extract_unit(unit)
        except (StructuredOutputError, LLMProviderError) as exc:
            logger.warning("Section %d (%s) failed: %s", unit.index, unit.title, exc)
            return {**entry, "status": "failed", "reason": str(exc), "concepts": []}
        return {
            **entry,
            "status": "ok",
            "reason": None,
            "concepts": [concept.model_dump() for concept in concepts],
        }

    async def _reduce(
        self,
        document: DocumentModel,
        chunks: Sequence[DocumentChunkModel],
        results: dict[str, dict[str, Any]],
    ) -> None:
        ordered = sorted(results.items(), key=lambda item: int(item[0]))
        failed = [
            FailedSection(
                section_index=int(index), section_title=entry["title"], reason=entry["reason"]
            ).model_dump()
            for index, entry in ordered
            if entry["status"] == "failed"
        ]
        succeeded = [entry for _, entry in ordered if entry["status"] == "ok"]
        if not succeeded:
            await self._update(
                document.id,
                status="failed",
                phase="done",
                failed_sections=failed,
                error="No section of the material could be processed.",
            )
            return

        extracted = [
            ExtractedConcept.model_validate(concept)
            for entry in succeeded
            for concept in entry["concepts"]
        ]

        async def on_phase(phase: str) -> None:
            await self._update(document.id, phase=phase, current_section=None)

        try:
            graph = await self._pipeline.build_graph(
                extracted,
                fallback_topic=_fallback_topic(document, chunks),
                valid_chunk_indices={chunk.chunk_index for chunk in chunks},
                on_phase=on_phase,
            )
        except (
            MindMapGenerationError,
            StructuredOutputError,
            LLMProviderError,
            EmbeddingProviderError,
        ) as exc:
            logger.warning("Mind map reduce failed for '%s': %s", document.name, exc)
            await self._update(
                document.id, status="failed", phase="done", failed_sections=failed, error=str(exc)
            )
            return

        await self._update(
            document.id,
            status="partial" if failed else "ready",
            phase="done",
            failed_sections=failed,
            payload=graph.model_dump(mode="json"),
            error=None,
        )
        logger.info(
            "Mind map for '%s' is %s (%d nodes, %d failed sections).",
            document.name,
            "partial" if failed else "ready",
            len(graph.nodes),
            len(failed),
        )

    async def run(self, document_id: uuid.UUID) -> None:
        """Map every section, persisting progress after each one, then reduce."""
        try:
            document, chunks = await self._load_source(document_id)
            units = build_map_units(chunks)
            await self._update(
                document_id,
                status="processing",
                phase="mapping",
                progress_done=0,
                progress_total=len(units),
                current_section=None,
            )
            results: dict[str, dict[str, Any]] = {}
            for unit in units:
                await self._update(document_id, progress_done=unit.index, current_section=unit.title)
                results[str(unit.index)] = await self._map_unit(unit)
                await self._update(
                    document_id, section_results=dict(results), progress_done=unit.index + 1
                )
            await self._reduce(document, chunks, results)
        except Exception as exc:  # never leave a map stuck in 'processing'
            logger.exception("Unexpected error generating the mind map of %s.", document_id)
            await self._update(
                document_id, status="failed", phase="done", error=f"Unexpected error: {exc}"
            )

    async def run_section_retry(self, document_id: uuid.UUID, section_index: int) -> None:
        """Reprocess one failed section, then rebuild the map from all section results."""
        try:
            document, chunks = await self._load_source(document_id)
            async with self._session_factory() as session:
                mind_map = await self._load_map(session, document_id)
                results: dict[str, dict[str, Any]] = dict(mind_map.section_results) if mind_map else {}

            units = build_map_units(chunks)
            stored = results.get(str(section_index), {})
            if section_index >= len(units) or units[section_index].chunk_indices != stored.get(
                "chunk_indices"
            ):
                await self._update(
                    document_id,
                    status="failed",
                    phase="done",
                    error="The document sections changed. Generate the whole map again.",
                )
                return

            results[str(section_index)] = await self._map_unit(units[section_index])
            await self._update(document_id, section_results=dict(results), progress_done=1)
            await self._reduce(document, chunks, results)
        except Exception as exc:
            logger.exception("Unexpected error retrying section %d of %s.", section_index, document_id)
            await self._update(
                document_id, status="failed", phase="done", error=f"Unexpected error: {exc}"
            )
