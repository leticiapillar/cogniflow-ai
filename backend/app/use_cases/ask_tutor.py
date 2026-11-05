from collections.abc import Sequence
import logging
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.document_repository import DocumentRepository
from app.repositories.models import DocumentChunkModel, MindMapModel
from app.schemas.tutor import (
    NOT_FOUND_ANSWER,
    AskRequest,
    AskResponse,
    Citation,
    RelatedConcept,
    Term,
)
from app.services.embeddings import BaseEmbeddingProvider
from app.services.llm_provider import BaseLLMProvider, LLMProviderError
from app.services.rag_retriever import RAGRetriever, RetrievalResult
from app.services.structured_output import StructuredOutputError, generate_structured
from app.services.text_processing import prepare_chunk_text
from app.services.tutor import prompts
from app.services.tutor.llm_schemas import StandaloneQuestion, TutorAnswer
from app.use_cases.errors import DocumentNotFoundError, EmbeddingModelMismatchError

logger = logging.getLogger("cogniflow.use_cases.ask_tutor")

MAX_KEY_POINTS = 3
MAX_TERMS = 5
MAX_PINNED_CHUNKS = 5
MAX_RELATED_CONCEPTS = 2
EXCERPT_CHARS = 240
MAX_STANDALONE_QUESTION_CHARS = 400


class TutorUnavailableError(RuntimeError):
    """Raised when no valid answer can be produced by the LLM (never answered without it)."""


class MindMapNodeNotFoundError(LookupError):
    """Raised when the question refers to a node that is not in the current mind map."""


def _excerpt(chunk: DocumentChunkModel) -> str:
    text = prepare_chunk_text(chunk.content) or chunk.content.strip()
    return text if len(text) <= EXCERPT_CHARS else text[: EXCERPT_CHARS - 1].rstrip() + "…"


class AskTutorUseCase:
    """Answers a student's question with RAG restricted to one document."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: BaseEmbeddingProvider,
        llm_provider: BaseLLMProvider,
        top_k: int,
        min_similarity: float,
    ) -> None:
        self._session = session
        self._repository = DocumentRepository(session)
        self._embedding_provider = embedding_provider
        self._llm = llm_provider
        self._retriever = RAGRetriever(self._repository, embedding_provider)
        self._top_k = top_k
        self._min_similarity = min_similarity

    async def _load_map_nodes(self, document_id: uuid.UUID) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(MindMapModel.payload).where(MindMapModel.document_id == document_id)
        )
        payload = result.scalar_one_or_none()
        return list(payload.get("nodes", [])) if payload else []

    async def _standalone_question(self, request: AskRequest) -> str:
        if not request.history:
            return request.question

        def validate(output: StandaloneQuestion) -> tuple[StandaloneQuestion, list[str]]:
            question = output.question.strip()
            if not question:
                return output, ["o campo question está vazio."]
            if len(question) > MAX_STANDALONE_QUESTION_CHARS:
                return output, [f"escreva a pergunta com no máximo {MAX_STANDALONE_QUESTION_CHARS} caracteres."]
            return StandaloneQuestion(question=question), []

        rewritten = await generate_structured(
            self._llm,
            prompts.REWRITE_SYSTEM_PROMPT,
            prompts.build_rewrite_prompt(request.history, request.question),
            StandaloneQuestion,
            validate,
        )
        logger.info("Rewrote question %r as %r.", request.question, rewritten.question)
        return rewritten.question

    def _not_found(
        self, retrieval: RetrievalResult | None, nodes: Sequence[dict[str, Any]]
    ) -> AskResponse:
        """Fixed answer plus concepts of the map that share the closest chunks."""
        concepts = [n for n in nodes if n.get("data", {}).get("category") == "concept"]
        rank = {index: position for position, index in enumerate(retrieval.ranked_indices if retrieval else [])}

        def closeness(node: dict[str, Any]) -> int:
            positions = [rank[i] for i in node["data"].get("source_chunks", []) if i in rank]
            return min(positions, default=len(rank) + 1)

        related = sorted((n for n in concepts if closeness(n) <= len(rank)), key=closeness)
        if not related:
            related = [n for n in nodes if n.get("data", {}).get("category") == "topic"]
        return AskResponse(
            found_in_material=False,
            answer=NOT_FOUND_ANSWER,
            related_concepts=[
                RelatedConcept(node_id=n["id"], label=n["data"]["label"])
                for n in related[:MAX_RELATED_CONCEPTS]
            ],
        )

    async def ask(self, document_id: uuid.UUID, request: AskRequest) -> AskResponse:
        document = await self._repository.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError(f"Document '{document_id}' not found.")
        if (
            document.embedding_model != self._embedding_provider.model_name
            or document.embedding_dimension != self._embedding_provider.dimension
        ):
            raise EmbeddingModelMismatchError(
                document_name=document.name,
                stored_model=document.embedding_model,
                current_model=self._embedding_provider.model_name,
            )

        nodes = await self._load_map_nodes(document_id)
        node = None
        if request.node_id:
            node = next((n for n in nodes if n.get("id") == request.node_id), None)
            if node is None:
                raise MindMapNodeNotFoundError(
                    f"Node '{request.node_id}' is not in the current mind map of this document."
                )
        concept_label = node["data"]["label"] if node else None
        pinned = node["data"].get("source_chunks", [])[:MAX_PINNED_CHUNKS] if node else []

        try:
            question = await self._standalone_question(request)
            search_text = f"{concept_label}: {question}" if concept_label else question
            retrieval = await self._retriever.retrieve(
                search_text, document_id, top_k=self._top_k, pinned_indices=pinned
            )
        except (StructuredOutputError, LLMProviderError) as exc:
            raise TutorUnavailableError(str(exc)) from exc

        # A question about a map node is grounded on the node's own chunks.
        unrelated = retrieval.best_similarity is None or retrieval.best_similarity < self._min_similarity
        if not retrieval.chunks or (unrelated and not pinned):
            logger.info(
                "Question unrelated to the material (best_similarity=%s < %.2f).",
                retrieval.best_similarity,
                self._min_similarity,
            )
            return self._not_found(retrieval, nodes)

        chunks_by_index = {chunk.chunk_index: chunk for chunk in retrieval.chunks}

        def validate(output: TutorAnswer) -> tuple[TutorAnswer, list[str]]:
            if not output.found_in_material:
                return output, []
            problems: list[str] = []
            if not output.answer.strip():
                problems.append("o campo answer está vazio.")
            cited = list(dict.fromkeys(output.citations))
            unknown = [index for index in cited if index not in chunks_by_index]
            if not cited:
                problems.append("informe em citations os trechos que sustentam a resposta.")
            elif unknown:
                problems.append(
                    f"os trechos {unknown} não estão no material. Use apenas {sorted(chunks_by_index)}."
                )
            normalized = output.model_copy(
                update={
                    "answer": output.answer.strip(),
                    "key_points": [p.strip() for p in output.key_points if p.strip()][:MAX_KEY_POINTS],
                    "example": output.example.strip(),
                    "terms": [t for t in output.terms if t.term.strip() and t.definition.strip()][:MAX_TERMS],
                    "citations": cited,
                }
            )
            return normalized, problems

        try:
            answer = await generate_structured(
                self._llm,
                prompts.ANSWER_SYSTEM_PROMPT,
                prompts.build_answer_prompt(question, retrieval.chunks, request.history, concept_label),
                TutorAnswer,
                validate,
            )
        except (StructuredOutputError, LLMProviderError) as exc:
            raise TutorUnavailableError(str(exc)) from exc

        if not answer.found_in_material:
            return self._not_found(retrieval, nodes)

        return AskResponse(
            found_in_material=True,
            answer=answer.answer,
            key_points=answer.key_points,
            example=answer.example or None,
            terms=[Term(term=t.term.strip(), definition=t.definition.strip()) for t in answer.terms],
            citations=[
                Citation(
                    chunk_index=index,
                    page_start=chunks_by_index[index].page_start,
                    page_end=chunks_by_index[index].page_end,
                    section_title=chunks_by_index[index].section_title,
                    excerpt=_excerpt(chunks_by_index[index]),
                )
                for index in answer.citations
            ],
        )

