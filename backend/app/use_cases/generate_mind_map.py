import logging
import time

from app.core.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.mind_map import GenerateMapRequest, GenerateMapResponse
from app.services.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.services.llm_provider import (
    BaseLLMProvider,
    ContextGroundedLocalLLMProvider,
    get_llm_provider,
)
from app.services.output_validator import (
    LLMOutputValidationError,
    validate_and_parse_mind_map_json,
)
from app.services.prompts import MIND_MAP_SYSTEM_PROMPT, build_user_prompt
from app.services.rag_retriever import RAGRetriever
from app.use_cases.errors import EmbeddingModelMismatchError

logger = logging.getLogger("cogniflow.use_cases.generate_mind_map")


class GenerateMindMapUseCase:
    """Use case orchestrating RAG similarity retrieval, LLM JSON generation, and output validation."""

    def __init__(
        self,
        repository: DocumentRepository,
        llm_provider: BaseLLMProvider | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings or get_settings()
        self._llm_provider = llm_provider or get_llm_provider(settings=self._settings)
        self._embedding_provider = embedding_provider or get_embedding_provider(
            self._settings
        )
        self._retriever = RAGRetriever(
            repository=repository,
            embedding_provider=self._embedding_provider,
        )

    async def _retrieve_context(self, request: GenerateMapRequest) -> list[str]:
        """Retrieve grounding chunks, refusing documents embedded with another model."""
        document_id = None
        if request.document_name:
            document = await self._repository.get_document_by_name(request.document_name)
            if document is None:
                logger.warning(
                    "Document '%s' not found; generating without context.",
                    request.document_name,
                )
                return []
            if (
                document.embedding_model != self._embedding_provider.model_name
                or document.embedding_dimension != self._embedding_provider.dimension
            ):
                raise EmbeddingModelMismatchError(
                    document_name=document.name,
                    stored_model=document.embedding_model,
                    current_model=self._embedding_provider.model_name,
                )
            document_id = document.id

        records = await self._retriever.retrieve_relevant_chunks(
            query=request.query,
            top_k=request.top_k,
            document_id=document_id,
        )
        return [record.content for record in records]

    async def execute(self, request: GenerateMapRequest) -> GenerateMapResponse:
        """Execute RAG similarity search, invoke LLM in JSON mode, and validate output contract."""
        start_time = time.perf_counter()
        logger.info(
            "Executing RAG mind map generation for query='%s' (top_k=%d, document=%s).",
            request.query,
            request.top_k,
            request.document_name,
        )

        context_chunks = await self._retrieve_context(request)

        user_prompt = build_user_prompt(
            query=request.query,
            context_chunks=context_chunks,
        )

        raw_llm_json = await self._llm_provider.generate_mind_map_json(
            system_prompt=MIND_MAP_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            query=request.query,
            context_chunks=context_chunks,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        try:
            validated_response = validate_and_parse_mind_map_json(
                raw_output=raw_llm_json,
                source_chunks_used=len(context_chunks),
                generation_latency_ms=elapsed_ms,
                expected_topic=request.query,
            )
        except LLMOutputValidationError as exc:
            if isinstance(self._llm_provider, ContextGroundedLocalLLMProvider):
                raise
            logger.warning(
                "LLM output failed validation (%s); falling back to ContextGroundedLocalLLMProvider.",
                exc,
            )
            fallback_json = await ContextGroundedLocalLLMProvider().generate_mind_map_json(
                system_prompt=MIND_MAP_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                query=request.query,
                context_chunks=context_chunks,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            validated_response = validate_and_parse_mind_map_json(
                raw_output=fallback_json,
                source_chunks_used=len(context_chunks),
                generation_latency_ms=elapsed_ms,
                expected_topic=request.query,
            )
        logger.info(
            "Generated validated mind map with %d nodes and %d edges (chunks=%d, latency=%.2f ms).",
            len(validated_response.nodes),
            len(validated_response.edges),
            validated_response.source_chunks_used,
            validated_response.generation_latency_ms,
        )
        return validated_response
