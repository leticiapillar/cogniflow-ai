import json
from pathlib import Path

from httpx import AsyncClient
import pytest

from app.core.config import Settings
from app.repositories.models import DocumentChunkModel, EMBEDDING_DIMENSION
from app.services.embeddings import EmbeddingService
from app.services.llm_provider import (
    GEMINI_MIND_MAP_RESPONSE_SCHEMA,
    ContextGroundedLocalLLMProvider,
    GeminiLLMProvider,
    OllamaLLMProvider,
    get_llm_provider,
)
from app.services.output_validator import (
    LLMOutputValidationError,
    validate_and_parse_mind_map_json,
)
from app.services.pedagogical_structurer import (
    build_pedagogical_outline,
    compile_outline_to_mind_map_dict,
    normalize_llm_mind_map_json,
)
from app.services.prompts import MIND_MAP_SYSTEM_PROMPT, build_user_prompt
from app.services.rag_retriever import RAGRetriever

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
    assert "PEDAGOGICAL HIERARCHY AND TAXONOMY RULES" in MIND_MAP_SYSTEM_PROMPT
    assert '"category": "topic"' in MIND_MAP_SYSTEM_PROMPT

    user_prompt = build_user_prompt(
        query="Clean Architecture and pgvector",
        context_chunks=["FastAPI orchestrator with PostgreSQL and pgvector."],
    )
    assert "<USER_QUERY>" in user_prompt
    assert "[Chunk 1 of 1]" in user_prompt
    assert "FastAPI orchestrator with PostgreSQL and pgvector." in user_prompt
    assert "multi-level hierarchy" in user_prompt
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

    duplicate_edge_payload = json.dumps(
        {
            "topic": "Biology",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {"label": "Cell", "summary": "Basic unit", "category": "root"},
                },
                {
                    "id": "node-1",
                    "type": "default",
                    "data": {"label": "Nucleus", "summary": "Control", "category": "concept"},
                },
            ],
            "edges": [
                {"id": "edge-dup", "source": "node-root", "target": "node-1"},
                {"id": "edge-dup", "source": "node-root", "target": "node-1"},
            ],
        }
    )
    with pytest.raises(LLMOutputValidationError, match="duplicate edge id"):
        validate_and_parse_mind_map_json(duplicate_edge_payload)


def test_output_validator_connects_orphan_nodes_to_root() -> None:
    """Verify disconnected valid nodes are automatically attached to the root node."""
    orphan_payload = json.dumps(
        {
            "topic": "Inteligência Artificial Generativa",
            "nodes": [
                {
                    "id": "node-root",
                    "type": "input",
                    "data": {
                        "label": "Inteligência Artificial Generativa",
                        "summary": "Criação de conteúdo novo.",
                        "category": "root",
                    },
                },
                {
                    "id": "node-topic-1",
                    "type": "default",
                    "data": {
                        "label": "Fundamentos da IAG",
                        "summary": "Três pilares principais.",
                        "category": "topic",
                    },
                },
                {
                    "id": "node-orphan",
                    "type": "default",
                    "data": {
                        "label": "Evolução Histórica",
                        "summary": "Marcos de 1956 a 2022+.",
                        "category": "topic",
                    },
                },
            ],
            "edges": [
                {
                    "id": "edge-1",
                    "source": "node-root",
                    "target": "node-topic-1",
                    "label": "divide-se em",
                }
            ],
        }
    )
    validated = validate_and_parse_mind_map_json(orphan_payload)
    assert len(validated.edges) == 2
    assert any(
        edge.source == "node-root" and edge.target == "node-orphan"
        for edge in validated.edges
    )


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
            "Pipeline RAG: Extração de PDF, sanitização, chunking semântico e embeddings.",
            "Validação Estrutural: Modelos Pydantic garantem integridade de nós e arestas.",
        ],
    )
    validated = validate_and_parse_mind_map_json(raw_json, source_chunks_used=4)
    assert len(validated.nodes) >= 5
    assert len(validated.edges) >= 4
    categories = {node.data.category for node in validated.nodes}
    assert "root" in categories
    assert "topic" in categories
    assert "concept" in categories
    assert GEMINI_MIND_MAP_RESPONSE_SCHEMA["type"] == "OBJECT"
    assert "nodes" in GEMINI_MIND_MAP_RESPONSE_SCHEMA["properties"]  # type: ignore[operator]


@pytest.mark.asyncio
async def test_rag_retriever_expands_neighbor_window_and_orders_canonically() -> None:
    """Verify RAGRetriever expands adjacent chunks and returns results in ascending chunk_index order."""
    dummy_vec = [0.1] * EMBEDDING_DIMENSION
    all_chunks = {
        idx: DocumentChunkModel(
            document_name="genai_lecture.pdf",
            chunk_index=idx,
            content=f"Section {idx} content",
            embedding=dummy_vec,
        )
        for idx in range(6)
    }

    class FakeRepository:
        async def search_similar_chunks(
            self,
            query_embedding: list[float],
            top_k: int = 5,
            document_name: str | None = None,
        ) -> list[DocumentChunkModel]:
            # Simulate cosine similarity returning out-of-order chunks (4, then 1)
            return [all_chunks[4], all_chunks[1]]

        async def get_chunks_by_indices(
            self,
            document_name: str,
            chunk_indices: list[int],
        ) -> list[DocumentChunkModel]:
            return [all_chunks[i] for i in sorted(chunk_indices) if i in all_chunks]

    retriever = RAGRetriever(
        repository=FakeRepository(),  # type: ignore[arg-type]
        embedding_service=EmbeddingService(Settings(EMBEDDING_PROVIDER="local")),
    )
    results = await retriever.retrieve_relevant_chunks(
        query="Generative AI Foundations and History",
        top_k=2,
        document_name="genai_lecture.pdf",
        neighbor_window=1,
    )

    retrieved_indices = [chunk.chunk_index for chunk in results]
    # Primary (4, 1) + neighbors (0, 2, 3, 5) sorted canonically -> [0, 1, 2, 3, 4, 5]
    assert retrieved_indices == [0, 1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_rag_retriever_stratifies_coverage_for_broad_top_k() -> None:
    """Verify RAGRetriever includes chunks across the document when top_k >= 10."""
    dummy_vec = [0.1] * EMBEDDING_DIMENSION
    all_chunks = [
        DocumentChunkModel(
            document_name="genai_lecture.pdf",
            chunk_index=idx,
            content=f"Section {idx} content",
            embedding=dummy_vec,
        )
        for idx in range(12)
    ]

    class BroadFakeRepository:
        async def search_similar_chunks(
            self,
            query_embedding: list[float],
            top_k: int = 5,
            document_name: str | None = None,
        ) -> list[DocumentChunkModel]:
            return all_chunks[:2]

        async def get_chunks_by_indices(
            self,
            document_name: str,
            chunk_indices: list[int],
        ) -> list[DocumentChunkModel]:
            return [all_chunks[i] for i in sorted(chunk_indices) if 0 <= i < len(all_chunks)]

        async def get_chunks_by_document(
            self,
            document_name: str,
        ) -> list[DocumentChunkModel]:
            return all_chunks

    retriever = RAGRetriever(
        repository=BroadFakeRepository(),  # type: ignore[arg-type]
        embedding_service=EmbeddingService(Settings(EMBEDDING_PROVIDER="local")),
    )
    results = await retriever.retrieve_relevant_chunks(
        query="O que é IAG?",
        top_k=15,
        document_name="genai_lecture.pdf",
    )

    assert [chunk.chunk_index for chunk in results] == list(range(12))


def test_pedagogical_structurer_reflows_wrapped_pdf_and_filters_author_noise() -> None:
    """Verify wrapped PDF lines, author titles ('Prof. Dr.'), and dangling prepositions are cleaned."""
    wrapped_iag_chunks = [
        (
            "Fundamentos e Evolução da Inteligência Artificial Generativa\n"
            "Prof. Dr. Marcos Leandro Hoffmann Souza\n"
            "## Definição e Distinção\n"
            "A Inteligência Artificial Generativa (IAG ou\n"
            "GenAI) destaca-se pela\n"
            "sua capacidade de criar conteúdo novo e original.\n"
            "Diferença da IA Tradicional: Enquanto a IA tradicional foca em classificação e previsão, "
            "a IAG foca na criação de texto, imagens e código."
        ),
        (
            "## Evolução Histórica\n"
            "Em 1956, ocorreu a Fundação da IA na conferência de Dartmouth.\n"
            "Em 2014, surgiram as GANs (Redes Adversariais Generativas) para criação de imagens.\n"
            "Em 2017, a Arquitetura Transformer revolucionou o processamento de linguagem natural."
        ),
    ]

    outline = build_pedagogical_outline(
        query="o que é iag?",
        context_chunks=wrapped_iag_chunks,
    )
    assert outline.language == "pt"
    assert len(outline.direct_synthesis) >= 30
    assert len(outline.axes) >= 2

    compiled = compile_outline_to_mind_map_dict(outline)
    validated = validate_and_parse_mind_map_json(
        json.dumps(compiled, ensure_ascii=False),
        source_chunks_used=2,
        expected_topic="o que é iag?",
    )

    labels = [node.data.label for node in validated.nodes]
    assert "Prof" not in labels
    assert not any(
        label.lower().split()[-1] in {"seus", "ou", "de", "dos"}
        for label in labels
        if label.split()
    )
    edge_labels = {edge.label for edge in validated.edges if edge.label}
    assert "structures into" not in edge_labels
    assert "encompasses" not in edge_labels


def test_normalize_llm_mind_map_json_compiles_outline_and_nested_children() -> None:
    """Verify LLM outline or nested node output is deterministically compiled into React Flow JSON."""
    raw_outline = json.dumps(
        {
            "topic": "o que é iag?",
            "synthesis": "A IAG é um ramo da IA focado na criação de novos conteúdos.",
            "branches": [
                {
                    "title": "Definição e Distinção",
                    "summary": "Conceito central e contraste com IA analítica.",
                    "relation": "divide-se em",
                    "concepts": [
                        {
                            "label": "Criação de Conteúdo Original",
                            "summary": "Gera texto, código, áudio e imagens inéditas.",
                            "category": "concept",
                            "relation": "caracteriza-se por",
                        },
                        {
                            "label": "Exemplos: ChatGPT e DALL-E",
                            "summary": "Modelos generativos de texto e imagem.",
                            "category": "example",
                            "relation": "exemplificado por",
                        },
                    ],
                }
            ],
        },
        ensure_ascii=False,
    )

    normalized = normalize_llm_mind_map_json(
        raw_output=raw_outline,
        query="o que é iag?",
        context_chunks=["A IAG cria conteúdo novo."],
    )
    validated = validate_and_parse_mind_map_json(
        normalized,
        source_chunks_used=1,
        expected_topic="o que é iag?",
    )
    assert len(validated.nodes) == 4
    assert len(validated.edges) == 3
    assert validated.nodes[0].data.summary == "A IAG é um ramo da IA focado na criação de novos conteúdos."



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

