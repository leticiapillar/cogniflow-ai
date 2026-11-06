from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
import re
import time
import unicodedata
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.tutor import AskRequest
from app.services.embeddings import BaseEmbeddingProvider, EmbeddingProviderError
from app.services.evaluation_metrics import calculate_entity_recall
from app.services.ingestion_pipeline import IngestionOrchestrator
from app.services.llm_provider import BaseLLMProvider, LLMProviderError
from app.services.mind_map.pipeline import MindMapGenerationError, MindMapPipeline
from app.services.mind_map.units import build_map_units
from app.services.mind_map.validation import validate_mind_map_graph
from app.services.rag_retriever import RAGRetriever
from app.services.structured_output import StructuredOutputError
from app.use_cases.ask_tutor import AskTutorUseCase, TutorUnavailableError
from evaluation.accessibility import evaluate_texts
from evaluation.datasets import MapReference, TutorQuestion

TOKEN = re.compile(r"[a-z0-9]{4,}")


def _normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in folded if not unicodedata.combining(char))


# ---- Mind map --------------------------------------------------------------------------------


@dataclass
class MapResult:
    document: str
    status: str  # ready | partial | failed
    sections: int
    failed_sections: int
    seconds: float
    recall: float = 0.0
    missing_entities: list[str] = field(default_factory=list)
    nodes: int = 0
    topics: int = 0
    max_concepts_per_topic: int = 0
    structural_errors: list[str] = field(default_factory=list)
    label_grounding_rate: float | None = None
    texts: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    error: str | None = None


def _label_grounding(graph, chunk_text: dict[int, str]) -> float | None:  # type: ignore[no-untyped-def]
    """Share of concept/example labels whose significant words appear in their cited chunks."""
    checked = grounded = 0
    for node in graph.nodes:
        if node.data.category not in ("concept", "example"):
            continue
        tokens = TOKEN.findall(_normalize(node.data.label))
        if not tokens:
            continue
        cited = _normalize(" ".join(chunk_text.get(index, "") for index in node.data.source_chunks))
        checked += 1
        grounded += all(token[:5] in cited for token in tokens)  # prefix: plural/gender variations
    return grounded / checked if checked else None


async def evaluate_map(
    reference: MapReference,
    llm: BaseLLMProvider,
    embedder: BaseEmbeddingProvider,
    settings: Settings,
) -> MapResult:
    start = time.perf_counter()
    ingestion = await IngestionOrchestrator(embedding_provider=embedder, settings=settings).process_pdf_bytes(
        reference.pdf_bytes
    )
    units = build_map_units(ingestion.chunks)
    pipeline = MindMapPipeline(llm=llm, embedder=embedder)

    extracted, failed = [], 0
    for unit in units:
        try:
            extracted.extend(await pipeline.extract_unit(unit))
        except (StructuredOutputError, LLMProviderError):
            failed += 1

    result = MapResult(document=reference.name, status="failed", sections=len(units), failed_sections=failed, seconds=0.0)
    chunk_text = {chunk.chunk_index: chunk.content for chunk in ingestion.chunks}
    try:
        if failed == len(units):
            raise MindMapGenerationError("No section could be processed.")
        graph = await pipeline.build_graph(
            extracted,
            fallback_topic=reference.name,
            valid_chunk_indices=set(chunk_text),
        )
    except (MindMapGenerationError, StructuredOutputError, LLMProviderError, EmbeddingProviderError) as exc:
        result.error = str(exc)
        result.seconds = time.perf_counter() - start
        return result

    recall = calculate_entity_recall(expected_entities=reference.expected_entities, mind_map=graph)
    topics = [node for node in graph.nodes if node.data.category == "topic"]
    children = {topic.id: sum(1 for edge in graph.edges if edge.source == topic.id) for topic in topics}

    result.status = "partial" if failed else "ready"
    result.seconds = time.perf_counter() - start
    result.recall = recall.recall_score
    result.missing_entities = list(recall.missing_entities)
    result.nodes = len(graph.nodes)
    result.topics = len(topics)
    result.max_concepts_per_topic = max(children.values(), default=0)
    result.structural_errors = validate_mind_map_graph(graph, set(chunk_text))
    result.label_grounding_rate = _label_grounding(graph, chunk_text)
    result.texts = [node.data.summary or "" for node in graph.nodes]
    result.labels = [node.data.label for node in graph.nodes]
    return result


# ---- Tutor -----------------------------------------------------------------------------------


@dataclass
class TutorResult:
    question: str
    in_material: bool
    best_similarity: float | None
    llm_found: bool
    page_ok: bool
    keywords_ok: bool
    seconds: float
    answer: str = ""
    key_points: list[str] = field(default_factory=list)
    cited_pages: list[list[int]] = field(default_factory=list)
    error: str | None = None

    def found_with(self, threshold: float) -> bool:
        return self.llm_found and self.best_similarity is not None and self.best_similarity >= threshold

    def correct_with(self, threshold: float) -> bool:
        if not self.in_material:
            return not self.found_with(threshold)
        return self.found_with(threshold) and self.page_ok and self.keywords_ok


async def ingest_for_tutor(
    session_factory: async_sessionmaker[AsyncSession],
    pdf_bytes: bytes,
    embedder: BaseEmbeddingProvider,
    settings: Settings,
) -> uuid.UUID:
    from app.use_cases.ingest_document import IngestDocumentUseCase

    async with session_factory() as session:
        response = await IngestDocumentUseCase(
            DocumentRepository(session), embedding_provider=embedder, settings=settings
        ).execute_pdf_upload(filename="avaliacao-fotossintese.pdf", content_type="application/pdf", file_bytes=pdf_bytes)
    return response.document_id


async def evaluate_tutor(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: uuid.UUID,
    questions: Sequence[TutorQuestion],
    llm: BaseLLMProvider,
    embedder: BaseEmbeddingProvider,
    top_k: int,
) -> list[TutorResult]:
    """Ask every question with the threshold disabled, recording the best similarity apart.

    The final decision under any threshold is then `similarity >= threshold and llm_found`,
    which lets the threshold be calibrated offline without asking the model again.
    """
    results = []
    for question in questions:
        async with session_factory() as session:
            retrieval = await RAGRetriever(DocumentRepository(session), embedder).retrieve(
                question.question, document_id, top_k=top_k
            )
            use_case = AskTutorUseCase(
                session=session, embedding_provider=embedder, llm_provider=llm, top_k=top_k, min_similarity=-1.0
            )
            start = time.perf_counter()
            try:
                response = await use_case.ask(document_id, AskRequest(question=question.question))
            except TutorUnavailableError as exc:
                results.append(TutorResult(
                    question.question, question.in_material, retrieval.best_similarity, False, False, False,
                    time.perf_counter() - start, error=str(exc),
                ))
                continue

        seconds = time.perf_counter() - start
        text = _normalize(" ".join([response.answer, *response.key_points]))
        pages = [[c.page_start, c.page_end] for c in response.citations]
        results.append(TutorResult(
            question=question.question,
            in_material=question.in_material,
            best_similarity=retrieval.best_similarity,
            llm_found=response.found_in_material,
            page_ok=any(start <= page <= end for start, end in pages for page in question.pages),
            keywords_ok=any(_normalize(keyword) in text for keyword in question.answer_keywords),
            seconds=seconds,
            answer=response.answer,
            key_points=response.key_points,
            cited_pages=pages,
        ))
    return results


SAFETY_MARGIN = 0.15


def calibrate_threshold(results: Sequence[TutorResult], safety_margin: float = SAFETY_MARGIN) -> tuple[float, int]:
    """Highest threshold that never blocks an answerable question, with a safety margin.

    The threshold only saves an LLM call for questions clearly outside the subject;
    questions on the same subject but absent from the material must be refused by the
    model. Blocking a valid question is worse for the student than an extra call, so the
    threshold stays `safety_margin` below the least similar answerable question.
    """
    answerable = [r.best_similarity for r in results if r.in_material and r.best_similarity is not None]
    if not answerable:
        return -1.0, sum(r.correct_with(-1.0) for r in results)
    threshold = round(min(answerable) - safety_margin, 3)
    return threshold, sum(r.correct_with(threshold) for r in results)


def accessibility_of(texts: Sequence[str], labels: Sequence[str] = ()) -> dict[str, float | int | None]:
    return evaluate_texts(texts, labels).as_dict()


def as_dict(result: MapResult | TutorResult) -> dict[str, object]:
    return asdict(result)
