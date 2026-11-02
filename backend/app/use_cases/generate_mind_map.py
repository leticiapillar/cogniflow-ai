import logging
import time

from app.core.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.mind_map import GenerateMapRequest, GenerateMapResponse
from app.services.embeddings import EmbeddingService
from app.services.llm_provider import BaseLLMProvider, get_llm_provider
from app.services.output_validator import validate_and_parse_mind_map_json
from app.services.prompts import MIND_MAP_SYSTEM_PROMPT, build_user_prompt
from app.services.rag_retriever import RAGRetriever

logger = logging.getLogger("cogniflow.use_cases.generate_mind_map")


class GenerateMindMapUseCase:
    """Use case orchestrating RAG similarity retrieval, LLM JSON generation, and output validation."""

    def __init__(
        self,
        repository: DocumentRepository,
        llm_provider: BaseLLMProvider | None = None,
        retriever: RAGRetriever | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings or get_settings()
        self._llm_provider = llm_provider or get_llm_provider(settings=self._settings)
        self._retriever = retriever or RAGRetriever(
            repository=repository,
            embedding_service=EmbeddingService(settings=self._settings),
        )

    async def execute(self, request: GenerateMapRequest) -> GenerateMapResponse:
        """Execute RAG similarity search, invoke LLM in JSON mode, and validate output contract."""
        start_time = time.perf_counter()
        logger.info(
            "Executing RAG mind map generation for query='%s' (top_k=%d, document=%s).",
            request.query,
            request.top_k,
            request.document_name,
        )

        retrieved_records = await self._retriever.retrieve_relevant_chunks(
            query=request.query,
            top_k=request.top_k,
            document_name=request.document_name,
        )
        context_chunks = [record.content for record in retrieved_records]

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
        validated_response = validate_and_parse_mind_map_json(
            raw_output=raw_llm_json,
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
