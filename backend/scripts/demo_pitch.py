import asyncio
from pathlib import Path
import time

from app.schemas.mind_map import GenerateMapResponse
from app.services.evaluation_metrics import (
    RecallEvaluationResult,
    calculate_entity_recall,
    extract_reference_entities,
)
from app.services.embeddings import BaseEmbeddingProvider
from app.services.ingestion_pipeline import IngestionOrchestrator
from app.services.llm_provider import BaseLLMProvider, get_llm_provider
from app.services.output_validator import validate_and_parse_mind_map_json
from app.services.pdf_parser import extract_text_from_pdf_bytes
from app.services.prompts import MIND_MAP_SYSTEM_PROMPT, build_user_prompt


async def run_live_pitch_demo(
    pdf_path: Path,
    query: str = "Arquitetura Técnica CogniFlow AI RAG pgvector FastAPI",
    embedding_provider: BaseEmbeddingProvider | None = None,
    llm_provider: BaseLLMProvider | None = None,
) -> tuple[GenerateMapResponse, RecallEvaluationResult, float]:
    """Execute the end-to-end prototype conversion of a PDF for the live pitch."""
    start_time = time.perf_counter()
    pdf_bytes = pdf_path.read_bytes()

    orchestrator = IngestionOrchestrator(embedding_provider=embedding_provider)
    ingestion = await orchestrator.process_pdf_bytes(pdf_bytes)
    context_texts = [chunk.content for chunk in ingestion.chunks]

    user_prompt = build_user_prompt(query=query, context_chunks=context_texts)
    llm_provider = llm_provider or get_llm_provider()
    raw_json = await llm_provider.generate_mind_map_json(
        system_prompt=MIND_MAP_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        query=query,
        context_chunks=context_texts,
    )

    total_latency_ms = (time.perf_counter() - start_time) * 1000.0
    mind_map = validate_and_parse_mind_map_json(
        raw_output=raw_json,
        source_chunks_used=len(context_texts),
        generation_latency_ms=total_latency_ms,
    )

    extracted_full_text = extract_text_from_pdf_bytes(pdf_bytes)
    reference_entities = extract_reference_entities(extracted_full_text)[:6]
    recall_result = calculate_entity_recall(
        expected_entities=reference_entities,
        mind_map=mind_map,
    )
    return mind_map, recall_result, total_latency_ms


if __name__ == "__main__":
    default_pdf = Path(__file__).resolve().parents[2] / "Proposta_Projeto_CogniFlow_AI.pdf"
    response, recall, latency_ms = asyncio.run(run_live_pitch_demo(default_pdf))
    print("=== CogniFlow AI - Live Pitch Prototype Demo ===")
    print(f"PDF Document        : {default_pdf.name}")
    print(f"Topic               : {response.topic}")
    print(f"Semantic Chunks Used: {response.source_chunks_used}")
    print(f"Generated Nodes     : {len(response.nodes)}")
    print(f"Generated Edges     : {len(response.edges)}")
    print(f"Entity Recall Score : {recall.recall_score * 100:.1f}%")
    print(f"End-to-End Latency  : {latency_ms:.2f} ms (Target < 120,000 ms)")

