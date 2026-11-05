"""Live demo: turn a class PDF into a map-reduce mind map without touching the database.

Requires Ollama with the configured models (`docker compose up -d`):
    cd backend && ./.venv/bin/python -m scripts.demo_pitch
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
import time

from app.schemas.mind_map import MindMapGraph
from app.services.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.services.evaluation_metrics import (
    RecallEvaluationResult,
    calculate_entity_recall,
    extract_reference_entities,
)
from app.services.ingestion_pipeline import IngestionOrchestrator
from app.services.llm_provider import BaseLLMProvider, LLMProviderError, get_llm_provider
from app.services.mind_map.pipeline import MindMapPipeline
from app.services.mind_map.units import build_map_units
from app.services.pdf_parser import extract_text_from_pdf_bytes
from app.services.structured_output import StructuredOutputError


@dataclass(frozen=True)
class DemoResult:
    mind_map: MindMapGraph
    recall: RecallEvaluationResult
    sections: int
    failed_sections: int
    latency_ms: float


async def run_live_pitch_demo(
    pdf_path: Path,
    embedding_provider: BaseEmbeddingProvider | None = None,
    llm_provider: BaseLLMProvider | None = None,
) -> DemoResult:
    """Ingest a PDF in memory, map every section, and reduce into a mind map."""
    start_time = time.perf_counter()
    pdf_bytes = pdf_path.read_bytes()
    embedder = embedding_provider or get_embedding_provider()
    pipeline = MindMapPipeline(llm=llm_provider or get_llm_provider(), embedder=embedder)

    ingestion = await IngestionOrchestrator(embedding_provider=embedder).process_pdf_bytes(pdf_bytes)
    units = build_map_units(ingestion.chunks)

    extracted = []
    failed = 0
    for unit in units:
        try:
            extracted.extend(await pipeline.extract_unit(unit))
        except (StructuredOutputError, LLMProviderError):
            failed += 1

    mind_map = await pipeline.build_graph(
        extracted,
        fallback_topic=pdf_path.stem.replace("_", " "),
        valid_chunk_indices={chunk.chunk_index for chunk in ingestion.chunks},
    )
    reference_entities = extract_reference_entities(extract_text_from_pdf_bytes(pdf_bytes))[:6]
    return DemoResult(
        mind_map=mind_map,
        recall=calculate_entity_recall(expected_entities=reference_entities, mind_map=mind_map),
        sections=len(units),
        failed_sections=failed,
        latency_ms=(time.perf_counter() - start_time) * 1000.0,
    )


if __name__ == "__main__":
    default_pdf = Path(__file__).resolve().parents[2] / "Proposta_Projeto_CogniFlow_AI.pdf"
    result = asyncio.run(run_live_pitch_demo(default_pdf))
    print("=== CogniFlow AI - Live Pitch Prototype Demo ===")
    print(f"PDF Document        : {default_pdf.name}")
    print(f"Topic               : {result.mind_map.topic}")
    print(f"Sections (failed)   : {result.sections} ({result.failed_sections})")
    print(f"Generated Nodes     : {len(result.mind_map.nodes)}")
    print(f"Generated Edges     : {len(result.mind_map.edges)}")
    print(f"Entity Recall Score : {result.recall.recall_score * 100:.1f}%")
    print(f"End-to-End Latency  : {result.latency_ms:.2f} ms")
