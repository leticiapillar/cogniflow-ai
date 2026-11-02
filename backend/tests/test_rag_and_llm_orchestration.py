import json
from pathlib import Path

from httpx import AsyncClient
import pytest

from app.core.config import Settings
from app.services.llm_provider import (
    ContextGroundedLocalLLMProvider,
    GeminiLLMProvider,
    OllamaLLMProvider,
    get_llm_provider,
)
from app.services.output_validator import (
    LLMOutputValidationError,
    validate_and_parse_mind_map_json,
)
from app.services.prompts import MIND_MAP_SYSTEM_PROMPT, build_user_prompt

SAMPLE_PDF_PATH = (
    Path(__file__).resolve().parents[2] / "Proposta_Projeto_CogniFlow_AI.pdf"
)


def test_system_prompt_is_english_and_enforces_strict_json() -> None:
    """Verify the System Prompt is written in English and mandates strict JSON with nodes and edges."""
    assert "You MUST respond ONLY with a single valid JSON object" in MIND_MAP_SYSTEM_PROMPT
    assert '"nodes"' in MIND_MAP_SYSTEM_PROMPT
    assert '"edges"' in MIND_MAP_SYSTEM_PROMPT
    assert "<RETRIEVED_CONTEXT>" in MIND_MAP_SYSTEM_PROMPT
    assert 'The "topic" field MUST reproduce the text inside <USER_QUERY> exactly' in MIND_MAP_SYSTEM_PROMPT
    assert "same language used in <USER_QUERY>" in MIND_MAP_SYSTEM_PROMPT

    user_prompt = build_user_prompt(
        query="Clean Architecture and pgvector",
        context_chunks=["FastAPI orchestrator with PostgreSQL and pgvector."],
    )
    assert "<USER_QUERY>" in user_prompt
    assert "FastAPI orchestrator with PostgreSQL and pgvector." in user_prompt
    assert "Preserve the USER_QUERY exactly as the topic" in user_prompt


def test_output_validator_accepts_valid_json_and_strips_fences() -> None:
    """Verify output validator strips markdown fences and returns a validated GenerateMapResponse."""
    raw_fenced_json = """```json
    {
      "topic": "Clean Architecture",
      "nodes": [
        {
          "id": "node-root",
          "type": "input",
          "data": { "label": "Clean Architecture", "summary": "Separation of concerns.", "category": "root" },
          "position": { "x": 0, "y": 0 }
        },
        {
          "id": "node-1",
          "type": "default",
          "data": { "label": "Use Cases", "summary": "Business rules layer.", "category": "concept" },
          "position": { "x": 0, "y": 120 }
        }
      ],
      "edges": [
        {
          "id": "edge-1",
          "source": "node-root",
          "target": "node-1",
          "label": "contains",
          "animated": false
        }
      ]
    }
    ```"""
    validated = validate_and_parse_mind_map_json(raw_fenced_json, source_chunks_used=3)
    assert validated.topic == "Clean Architecture"
    assert len(validated.nodes) == 2
    assert len(validated.edges) == 1
    assert validated.source_chunks_used == 3


def test_output_validator_uses_the_requested_topic_instead_of_the_llm_title() -> None:
    raw_json = json.dumps(
        {
            "topic": "Unrelated English title",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {
                        "label": "Central Concept",
                        "summary": "Processo descrito no material.",
                        "category": "root",
                    },
                }
            ],
            "edges": [],
        }
    )

    validated = validate_and_parse_mind_map_json(
        raw_json,
        expected_topic="Como funciona a fotossíntese?",
    )

    assert validated.topic == "Como funciona a fotossíntese?"
    assert validated.nodes[0].data.label == "Como funciona a fotossíntese?"


def test_output_validator_limits_the_root_label_without_truncating_the_topic() -> None:
    long_topic = "Tema " * 100
    raw_json = json.dumps(
        {
            "topic": "Main topic title",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {
                        "label": "Central Concept",
                        "summary": "Resumo.",
                        "category": "root",
                    },
                }
            ],
            "edges": [],
        }
    )

    validated = validate_and_parse_mind_map_json(
        raw_json,
        expected_topic=long_topic,
    )

    assert validated.topic == long_topic
    assert validated.nodes[0].data.label == long_topic[:200]


def test_output_validator_rejects_dangling_edges_and_duplicate_nodes() -> None:
    """Verify structural hallucination guard rejects edges pointing to nonexistent nodes."""
    hallucinated_edge_payload = json.dumps(
        {
            "topic": "Biology",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {"label": "Cell", "summary": "Basic unit", "category": "root"},
                }
            ],
            "edges": [
                {
                    "id": "edge-invalid",
                    "source": "node-root",
                    "target": "node-nonexistent",
                    "label": "hallucinated",
                }
            ],
        }
    )
    with pytest.raises(LLMOutputValidationError, match="nonexistent target node"):
        validate_and_parse_mind_map_json(hallucinated_edge_payload)

    self_loop_payload = json.dumps(
        {
            "topic": "Biology",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {"label": "Cell", "summary": "Basic unit", "category": "root"},
                }
            ],
            "edges": [
                {
                    "id": "edge-loop",
                    "source": "node-root",
                    "target": "node-root",
                    "label": "loops",
                }
            ],
        }
    )
    with pytest.raises(LLMOutputValidationError, match="self-loop"):
        validate_and_parse_mind_map_json(self_loop_payload)


@pytest.mark.asyncio
async def test_llm_provider_abstraction_factory_and_switching() -> None:
    """Verify the LLM abstraction factory seamlessly switches between Local, Gemini, and Ollama."""
    local_provider = get_llm_provider(Settings(LLM_PROVIDER="local"))
    assert isinstance(local_provider, ContextGroundedLocalLLMProvider)

    gemini_provider = get_llm_provider(
        Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key")
    )
    assert isinstance(gemini_provider, GeminiLLMProvider)

    ollama_provider = get_llm_provider(
        Settings(LLM_PROVIDER="ollama", OLLAMA_LLM_MODEL="qwen2.5")
    )
    assert isinstance(ollama_provider, OllamaLLMProvider)

    raw_json = await local_provider.generate_mind_map_json(
        system_prompt=MIND_MAP_SYSTEM_PROMPT,
        user_prompt="test",
        query="Arquitetura Técnica CogniFlow",
        context_chunks=[
            "Backend Orquestrador: Construído em Python utilizando FastAPI e Clean Architecture.",
            "Banco de Dados Vetorial: PostgreSQL com a extensão pgvector via Docker Compose.",
        ],
    )
    validated = validate_and_parse_mind_map_json(raw_json, source_chunks_used=2)
    assert len(validated.nodes) >= 3
    assert len(validated.edges) >= 2


@pytest.mark.asyncio
async def test_end_to_end_rag_similarity_and_generate_map_from_ingested_pdf(
    async_client: AsyncClient,
) -> None:
    """Verify full RAG Phase 1 + Phase 2: ingest PDF into pgvector and generate grounded mind map."""
    pdf_bytes = SAMPLE_PDF_PATH.read_bytes()
    files = {
        "file": (
            "Proposta_Projeto_CogniFlow_AI.pdf",
            pdf_bytes,
            "application/pdf",
        )
    }
    ingest_res = await async_client.post("/api/documents/ingest", files=files)
    assert ingest_res.status_code == 201

    map_res = await async_client.post(
        "/api/generate-map",
        json={
            "query": "Arquitetura Técnica PostgreSQL pgvector FastAPI",
            "document_name": "Proposta_Projeto_CogniFlow_AI.pdf",
            "top_k": 3,
        },
    )
    assert map_res.status_code == 200
    data = map_res.json()
    assert data["source_chunks_used"] >= 1
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1

