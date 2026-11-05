from dataclasses import dataclass
import json

import httpx
import pytest

from app.core.config import Settings
from app.schemas.mind_map import MindMapGraph
from app.services.llm_provider import LLMProviderError, OllamaLLMProvider
from app.services.mind_map.llm_schemas import (
    ExtractedConcept,
    ExtractedExample,
    MapOrganization,
    SectionExtraction,
)
from app.services.mind_map.pipeline import MAX_ORGANIZATION_CONCEPTS, Concept, MindMapPipeline
from app.services.mind_map.units import MapUnit, build_map_units
from app.services.mind_map.validation import validate_mind_map_graph
from app.services.structured_output import StructuredOutputError, inline_json_schema
from tests.fakes.embeddings import FakeEmbeddingProvider
from tests.fakes.llm import FakeLLMProvider, ScriptedLLMProvider


@dataclass
class Chunk:
    chunk_index: int
    content: str
    section_title: str | None


def sentence(text: str, size: int) -> str:
    return (text + " ") * (size // (len(text) + 1))


def pipeline(llm=None) -> MindMapPipeline:  # type: ignore[no-untyped-def]
    return MindMapPipeline(llm=llm or FakeLLMProvider(), embedder=FakeEmbeddingProvider())


def extraction(*concepts: dict) -> str:  # type: ignore[type-arg]
    return json.dumps({"concepts": list(concepts)})


def concept(label: str, chunks: list[int], **extra: object) -> dict:  # type: ignore[type-arg]
    return {"label": label, "summary": f"{label} é um conceito da aula.", "source_chunks": chunks, **extra}


# ---- Units ---------------------------------------------------------------------------------


def test_units_merge_small_sections_and_split_large_ones() -> None:
    chunks = [
        Chunk(0, "Cloroplastos são organelas das plantas.", "Cloroplastos"),
        Chunk(1, "A clorofila absorve a luz do sol.", "Clorofila"),
        Chunk(2, sentence("A fase clara acontece nos tilacoides.", 3500), "Fase clara"),
        Chunk(3, sentence("O ciclo de Calvin produz glicose.", 3500), "Fase clara"),
        Chunk(4, "Prof. Dr. Fulano", "Créditos"),  # only metadata: dropped
    ]
    units = build_map_units(chunks)

    assert [u.chunk_indices for u in units] == [[0, 1], [2], [3]]
    assert units[0].title == "Cloroplastos / Clorofila"
    assert units[1].title == units[2].title == "Fase clara"
    assert [u.index for u in units] == [0, 1, 2]


# ---- Map -----------------------------------------------------------------------------------


async def test_extract_unit_retries_citing_the_validation_problem() -> None:
    llm = ScriptedLLMProvider(
        [
            extraction(concept("Clorofila", [99])),
            extraction(concept("Clorofila de", [4], examples=[{"label": "Folha verde", "summary": "A folha é verde."}])),
        ]
    )
    unit = MapUnit(index=0, titles=["Clorofila"], chunks=[(4, "A clorofila é um pigmento verde.")])

    concepts = await pipeline(llm).extract_unit(unit)

    assert [c.label for c in concepts] == ["Clorofila"]  # dangling "de" removed
    assert concepts[0].examples[0].label == "Folha verde"
    assert "[Trecho 4]" in llm.prompts[0]
    assert "ATENÇÃO" in llm.prompts[1] and "[99]" in llm.prompts[1]


async def test_extract_unit_gives_up_after_the_corrections() -> None:
    llm = ScriptedLLMProvider(["not json", "{}", extraction(concept("Clorofila", []))])
    unit = MapUnit(index=0, chunks=[(4, "A clorofila é um pigmento verde.")])
    with pytest.raises(StructuredOutputError, match="after 3 attempts"):
        await pipeline(llm).extract_unit(unit)


async def test_extract_unit_accepts_sections_without_study_content() -> None:
    llm = ScriptedLLMProvider([extraction()])
    unit = MapUnit(index=0, titles=["Bibliografia"], chunks=[(9, "Toda Biologia. Acesso em 2020.")])
    assert await pipeline(llm).extract_unit(unit) == []


async def test_llm_unavailability_is_not_swallowed() -> None:
    llm = ScriptedLLMProvider([LLMProviderError("down")])
    with pytest.raises(LLMProviderError):
        await pipeline(llm).extract_unit(MapUnit(index=0, chunks=[(0, "Texto da aula.")]))


# ---- Reduce --------------------------------------------------------------------------------


async def test_consolidate_merges_duplicates_and_keeps_first_appearance_order() -> None:
    extracted = [
        ExtractedConcept(label="Clorofila", summary="Pigmento verde.", source_chunks=[1],
                         examples=[ExtractedExample(label="Folha", summary="A folha é verde.")]),
        ExtractedConcept(label="Estômato", summary="Abertura da folha.", source_chunks=[2]),
        ExtractedConcept(label="clorofila", summary="Pigmento que absorve luz.", source_chunks=[5]),
        ExtractedConcept(label="Estômato", summary="Abertura da folha.", source_chunks=[7]),
    ]
    concepts = await pipeline().consolidate(extracted)

    assert [(c.id, c.label, c.source_chunks) for c in concepts] == [
        ("c1", "Clorofila", [1, 5]),
        ("c2", "Estômato", [2, 7]),
    ]
    assert [e.label for e in concepts[0].examples] == ["Folha"]


async def test_select_reduces_hierarchically_until_it_fits() -> None:
    llm = FakeLLMProvider()
    concepts = [Concept(id=f"c{i}", label=f"Conceito {i}", summary="Resumo.", source_chunks=[i]) for i in range(1, 61)]

    selected = await pipeline(llm).select(concepts)

    assert len(selected) <= MAX_ORGANIZATION_CONCEPTS
    assert [task for task, _ in llm.calls] == ["selection"] * 3
    assert [c.id for c in selected] == sorted((c.id for c in selected), key=lambda cid: int(cid[1:]))


async def test_organize_retries_when_axis_count_is_wrong() -> None:
    concepts = [Concept(id=f"c{i}", label=f"Conceito {i}", summary="Resumo.", source_chunks=[i]) for i in range(1, 5)]
    one_axis = {"topic": "Tema", "synthesis": "Frase.", "axes": [
        {"title": "Tudo", "summary": "Tudo.", "concepts": [{"id": "c1", "relation": "has_part"}]}]}
    llm = ScriptedLLMProvider([json.dumps(one_axis), json.dumps(FakeLLMProvider()._organization(
        "- c1 | a |\n- c2 | b |\n- c3 | c |\n- c4 | d |"))])

    organization = await pipeline(llm).organize(concepts)

    assert len(organization.axes) == 3
    assert "crie de 3 a 5 eixos" in llm.prompts[1]


async def test_organize_rejects_unknown_and_repeated_concepts() -> None:
    concepts = [Concept(id="c1", label="Clorofila", summary="Resumo.", source_chunks=[1])]
    bad = {"topic": "Tema", "synthesis": "Frase.", "axes": [
        {"title": "Clorofila", "summary": "x", "concepts": [{"id": "c1", "relation": "has_part"}, {"id": "c9", "relation": "has_part"}]}]}
    llm = ScriptedLLMProvider([json.dumps(bad)] * 3)
    with pytest.raises(StructuredOutputError) as error:
        await pipeline(llm).organize(concepts)
    assert "c9" in str(error.value) and "título é igual" in str(error.value)


def test_compile_builds_a_valid_tree_with_fixed_relation_verbs() -> None:
    concepts = [
        Concept(id="c1", label="Fase clara", summary="Usa luz.", source_chunks=[1],
                acronyms={"ATP": "Adenosina Trifosfato"},
                examples=[ExtractedExample(label="Quebra da água", summary="Libera oxigênio.")]),
        Concept(id="c2", label="Ciclo de Calvin", summary="Produz glicose.", source_chunks=[2, 3]),
    ]
    organization = MapOrganization.model_validate({
        "topic": "Fotossíntese", "synthesis": "As plantas produzem alimento.",
        "axes": [{"title": "Etapas", "summary": "Fases.", "concepts": [
            {"id": "c1", "relation": "has_part"}, {"id": "c2", "relation": "depends_on"}]}],
    })
    graph = MindMapPipeline.compile_graph(organization, concepts, fallback_topic="Aula")

    assert validate_mind_map_graph(graph, {1, 2, 3}) == []
    by_id = {node.id: node for node in graph.nodes}
    assert by_id["node-root"].data.source_chunks == [1, 2, 3]
    assert by_id["node-topic-1"].data.order == 1
    assert by_id["node-concept-c1"].data.acronyms == {"ATP": "Adenosina Trifosfato"}
    assert by_id["node-example-c1-1"].data.category == "example"
    labels = {(e.source, e.target): e.label for e in graph.edges}
    assert labels[("node-topic-1", "node-concept-c2")] == "depende de"
    assert labels[("node-concept-c1", "node-example-c1-1")] == "exemplificado por"


def test_graph_validation_reports_structural_problems() -> None:
    graph = MindMapGraph.model_validate({
        "topic": "Tema",
        "nodes": [
            {"id": "node-root", "type": "input", "data": {"label": "Raiz", "category": "root"}},
            {"id": "t1", "data": {"label": "Eixo", "category": "topic", "order": 1, "source_chunks": [1]}},
            {"id": "k1", "data": {"label": "Conceito", "category": "concept", "source_chunks": [42]}},
            {"id": "k2", "data": {"label": "Solto", "category": "concept", "source_chunks": [1]}},
        ],
        "edges": [
            {"id": "e1", "source": "node-root", "target": "t1", "relation": "has_part", "label": "inclui"},
            {"id": "e2", "source": "t1", "target": "k1", "relation": "causes", "label": "inclui"},
            {"id": "e3", "source": "node-root", "target": "k1", "relation": "has_part", "label": "inclui"},
        ],
    })
    errors = " | ".join(validate_mind_map_graph(graph, valid_chunk_indices={1}))

    assert "label does not match relation 'causes'" in errors
    assert "connects 'root' to 'concept'" in errors
    assert "'k1' has 2 parents" in errors
    assert "'k2' has 0 parents" in errors
    assert "nonexistent chunks [42]" in errors
    assert "not reachable from the root: ['k2']" in errors


async def test_build_graph_end_to_end_with_fakes() -> None:
    llm = FakeLLMProvider()
    units = [
        MapUnit(index=0, titles=["A"], chunks=[(0, "Cloroplastos são organelas."), (1, "Clorofila absorve luz.")]),
        MapUnit(index=1, titles=["B"], chunks=[(2, "Estômatos permitem a troca de gases."), (3, "Glicose é o alimento.")]),
    ]
    extracted = [c for unit in units for c in await pipeline(llm).extract_unit(unit)]
    phases: list[str] = []

    async def on_phase(phase: str) -> None:
        phases.append(phase)

    graph = await pipeline(llm).build_graph(extracted, "Aula", {0, 1, 2, 3}, on_phase)

    assert phases == ["consolidating", "organizing"]
    assert sum(1 for n in graph.nodes if n.data.category == "topic") == 3
    assert sum(1 for n in graph.nodes if n.data.category == "concept") == 4


# ---- Structured output plumbing --------------------------------------------------------------


def test_inline_json_schema_has_no_references() -> None:
    schema = inline_json_schema(SectionExtraction)
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    item = schema["properties"]["concepts"]["items"]
    assert set(item["required"]) == {"label", "summary", "source_chunks"}


async def test_ollama_llm_provider_sends_schema_and_retries_transient_errors() -> None:
    requests: list[dict] = []  # type: ignore[type-arg]
    statuses = iter([503])

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if next(statuses, 200) == 503:
            return httpx.Response(503, text="loading")
        return httpx.Response(200, json={"message": {"content": '{"concepts": []}'}})

    async def no_sleep(_: float) -> None:
        return None

    settings = Settings(OLLAMA_LLM_MODEL="llama3.2:3b", OLLAMA_NUM_CTX=8192, OLLAMA_NUM_PREDICT=1024)
    provider = OllamaLLMProvider(settings, transport=httpx.MockTransport(handler), sleep=no_sleep)
    schema = inline_json_schema(SectionExtraction)

    assert await provider.generate_json("sistema", "usuário", schema) == '{"concepts": []}'
    assert len(requests) == 2
    assert requests[1]["format"] == schema
    assert requests[1]["model"] == "llama3.2:3b"
    assert requests[1]["options"]["num_ctx"] == 8192
    assert requests[1]["options"]["num_predict"] == 1024
    assert requests[1]["messages"][0] == {"role": "system", "content": "sistema"}


async def test_ollama_llm_provider_fails_fast_on_client_errors() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(404, json={"error": "model not found"})

    provider = OllamaLLMProvider(Settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(LLMProviderError, match="HTTP 404"):
        await provider.generate_json("s", "u", {})
    assert attempts == 1
