"""Compare LLMs on the mind map and the tutor using the real Ollama models.

Requires Ollama with bge-m3 and the compared models, and Docker (a throwaway pgvector
container is used, so the local database is never touched):

    cd backend && ./.venv/bin/python -m evaluation --models llama3.2:3b qwen2.5:3b
"""

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import statistics

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from app.core.config import Settings
from app.core.database import initialize_database
from app.services.embeddings import get_embedding_provider
from app.services.llm_provider import OllamaLLMProvider
from evaluation.datasets import PHOTOSYNTHESIS_PDF, TUTOR_QUESTIONS, map_references
from evaluation.instrumentation import RecordingLLMProvider
from evaluation.runner import (
    accessibility_of,
    as_dict,
    calibrate_threshold,
    evaluate_map,
    evaluate_tutor,
    ingest_for_tutor,
)

RESULTS_DIR = Path(__file__).parent / "results"
logger = logging.getLogger("cogniflow.evaluation")


async def warm_up(llm: OllamaLLMProvider) -> None:
    """Load the model before timing anything (the first call includes loading it)."""
    await llm.generate_json("Responda em JSON.", "Diga ok.", {"type": "object", "properties": {"ok": {"type": "string"}}})


def summarize(model: str, llm: RecordingLLMProvider, maps: list, tutor: list, threshold: float, current: float) -> dict:
    in_material = [r for r in tutor if r.in_material]
    out_material = [r for r in tutor if not r.in_material]
    decided = lambda t: {  # noqa: E731
        "accuracy": sum(r.correct_with(t) for r in tutor) / len(tutor),
        "answered_correctly": sum(r.correct_with(t) for r in in_material),
        "refused_correctly": sum(r.correct_with(t) for r in out_material),
    }
    tutor_texts = [text for r in tutor if r.llm_found for text in [r.answer, *r.key_points]]
    return {
        "model": model,
        "json_first_attempt_rate": llm.first_attempt_rate(),
        "json_first_attempt_by_task": {
            task: llm.first_attempt_rate(task)
            for task in ("map_section", "selection", "organization", "tutor_answer")
            if llm.requests(task)
        },
        "map": {
            "documents": len(maps),
            "ready": sum(m.status == "ready" for m in maps),
            "partial": sum(m.status == "partial" for m in maps),
            "failed": sum(m.status == "failed" for m in maps),
            "section_failure_rate": sum(m.failed_sections for m in maps) / max(1, sum(m.sections for m in maps)),
            "mean_recall": statistics.mean(m.recall for m in maps) if maps else None,
            "structural_errors": sum(len(m.structural_errors) for m in maps),
            "mean_label_grounding": statistics.mean(
                [m.label_grounding_rate for m in maps if m.label_grounding_rate is not None] or [0.0]
            ),
            "mean_seconds": statistics.mean(m.seconds for m in maps) if maps else None,
            "accessibility": accessibility_of(
                [t for m in maps for t in m.texts], [label for m in maps for label in m.labels]
            ),
        },
        "tutor": {
            "questions": len(tutor),
            "errors": sum(r.error is not None for r in tutor),
            "llm_only": decided(-1.0),
            "with_current_threshold": {"threshold": current, **decided(current)},
            "with_calibrated_threshold": {"threshold": threshold, **decided(threshold)},
            "mean_seconds": statistics.mean(r.seconds for r in tutor) if tutor else None,
            "max_seconds": max((r.seconds for r in tutor), default=None),
            "accessibility": accessibility_of(tutor_texts),
        },
    }


async def main(models: list[str], academic: int, skip_map: bool, skip_tutor: bool, questions: int) -> Path:
    base = Settings()
    embedder = get_embedding_provider(base)
    references = map_references(academic)
    raw: dict[str, dict] = {}

    with PostgresContainer("pgvector/pgvector:pg16") as postgres:
        url = postgres.get_connection_url().replace("psycopg2", "asyncpg").replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(url)
        await initialize_database(engine)
        sessions = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        document_id = None
        if not skip_tutor:
            document_id = await ingest_for_tutor(sessions, PHOTOSYNTHESIS_PDF.read_bytes(), embedder, base)

        for model in models:
            settings = Settings(OLLAMA_LLM_MODEL=model)
            inner = OllamaLLMProvider(settings)
            logger.info("Warming up %s...", model)
            await warm_up(inner)
            llm = RecordingLLMProvider(inner)

            maps = []
            if not skip_map:
                for reference in references:
                    logger.info("[%s] mind map of %s", model, reference.name)
                    maps.append(await evaluate_map(reference, llm, embedder, settings))
            tutor = []
            if document_id is not None:
                logger.info("[%s] tutor: %d questions", model, len(TUTOR_QUESTIONS[:questions]))
                tutor = await evaluate_tutor(sessions, document_id, TUTOR_QUESTIONS[:questions], llm, embedder, base.tutor_top_k)
            raw[model] = {"llm": llm, "maps": maps, "tutor": tutor}

        await engine.dispose()

    all_tutor = [r for run in raw.values() for r in run["tutor"]]
    threshold, _ = calibrate_threshold(all_tutor) if all_tutor else (base.tutor_min_similarity, 0)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": embedder.model_name,
        "calibrated_threshold": threshold,
        "current_threshold": base.tutor_min_similarity,
        "summaries": [
            summarize(model, run["llm"], run["maps"], run["tutor"], threshold, base.tutor_min_similarity)
            for model, run in raw.items()
        ],
        "details": {
            model: {
                "maps": [{k: v for k, v in as_dict(m).items() if k != "texts"} for m in run["maps"]],
                "tutor": [as_dict(r) for r in run["tutor"]],
                "calls": [call.__dict__ for call in run["llm"].calls],
            }
            for model, run in raw.items()
        },
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"evaluation-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["llama3.2:3b", "qwen2.5:3b"])
    parser.add_argument("--academic", type=int, default=2, help="synthetic handouts added to the map evaluation")
    parser.add_argument("--skip-map", action="store_true")
    parser.add_argument("--skip-tutor", action="store_true")
    parser.add_argument("--questions", type=int, default=len(TUTOR_QUESTIONS), help="limit tutor questions (smoke runs)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for noisy in ("httpx", "cogniflow.services", "cogniflow.repository", "testcontainers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    output = asyncio.run(main(args.models, args.academic, args.skip_map, args.skip_tutor, args.questions))
    print(f"Results written to {output}")
