from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
import logging
import math

from app.schemas.mind_map import (
    RELATION_LABELS,
    MindMapEdge,
    MindMapGraph,
    MindMapNode,
    MindMapNodeData,
)
from app.services.embeddings import BaseEmbeddingProvider
from app.services.llm_provider import BaseLLMProvider
from app.services.mind_map import prompts
from app.services.mind_map.llm_schemas import (
    ConceptSelection,
    ExtractedConcept,
    ExtractedExample,
    MapOrganization,
    SectionExtraction,
)
from app.services.mind_map.units import MapUnit
from app.services.mind_map.validation import (
    MAX_CONCEPTS_PER_TOPIC,
    MAX_EXAMPLES_PER_CONCEPT,
    MAX_TOPICS,
    validate_mind_map_graph,
)
from app.services.structured_output import generate_structured
from app.services.text_processing import clean_concept_label

logger = logging.getLogger("cogniflow.services.mind_map.pipeline")

MAX_CONCEPTS_PER_UNIT = 8
MIN_TOPICS = 3
# Upper bound of concepts in the final organization prompt (5 axes x 5 concepts).
MAX_ORGANIZATION_CONCEPTS = MAX_TOPICS * MAX_CONCEPTS_PER_TOPIC
DEDUP_SIMILARITY_THRESHOLD = 0.85
SUMMARY_PREVIEW_CHARS = 140
SUMMARY_MAX_CHARS = 600

PhaseCallback = Callable[[str], Awaitable[None]]


class MindMapGenerationError(RuntimeError):
    """Raised when the reduce steps cannot build a valid mind map."""


@dataclass
class Concept:
    """A concept after merging duplicates across sections."""

    id: str
    label: str
    summary: str
    source_chunks: list[int]
    acronyms: dict[str, str] = field(default_factory=dict)
    examples: list[ExtractedExample] = field(default_factory=list)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _preview(concepts: Sequence[Concept]) -> list[tuple[str, str, str]]:
    return [(c.id, c.label, c.summary[:SUMMARY_PREVIEW_CHARS]) for c in concepts]


class MindMapPipeline:
    """Map (one LLM call per section) and reduce (dedupe + LLM organization) steps."""

    def __init__(self, llm: BaseLLMProvider, embedder: BaseEmbeddingProvider) -> None:
        self._llm = llm
        self._embedder = embedder

    # ---- Map -------------------------------------------------------------------------

    async def extract_unit(self, unit: MapUnit) -> list[ExtractedConcept]:
        """Key concepts of one section, each citing chunks that belong to the section."""
        allowed_chunks = set(unit.chunk_indices)

        def validate(output: SectionExtraction) -> tuple[SectionExtraction, list[str]]:
            problems: list[str] = []
            cleaned: list[ExtractedConcept] = []
            for position, concept in enumerate(output.concepts[:MAX_CONCEPTS_PER_UNIT], start=1):
                label = clean_concept_label(concept.label)
                summary = concept.summary.strip()
                if not label:
                    problems.append(f"conceito {position}: o campo label está vazio.")
                if not summary:
                    problems.append(f"conceito {position}: o campo summary está vazio.")
                cited = sorted(set(concept.source_chunks))
                unknown = [index for index in cited if index not in allowed_chunks]
                if not cited:
                    problems.append(f"conceito {position}: source_chunks está vazio.")
                elif unknown:
                    problems.append(
                        f"conceito {position}: os trechos {unknown} não existem nesta seção. "
                        f"Use apenas {sorted(allowed_chunks)}."
                    )
                examples = [
                    ExtractedExample(label=clean_concept_label(e.label), summary=e.summary.strip())
                    for e in concept.examples[:MAX_EXAMPLES_PER_CONCEPT]
                    if clean_concept_label(e.label) and e.summary.strip()
                ]
                cleaned.append(
                    concept.model_copy(
                        update={
                            "label": label,
                            "summary": summary,
                            "source_chunks": cited,
                            "examples": examples,
                        }
                    )
                )
            return SectionExtraction(concepts=cleaned), problems

        system_prompt = prompts.EXTRACTION_SYSTEM_PROMPT.format(max_concepts=MAX_CONCEPTS_PER_UNIT)
        result = await generate_structured(
            self._llm,
            system_prompt,
            prompts.build_extraction_prompt(unit),
            SectionExtraction,
            validate,
        )
        return result.concepts

    # ---- Reduce 1: deterministic deduplication ------------------------------------------

    async def consolidate(self, extracted: Sequence[ExtractedConcept]) -> list[Concept]:
        """Merge duplicated concepts across sections by embedding similarity, keeping order."""
        if not extracted:
            return []
        vectors = await self._embedder.embed_documents(
            [f"{concept.label}. {concept.summary}" for concept in extracted]
        )
        merged: list[tuple[list[float], Concept]] = []
        for concept, vector in zip(extracted, vectors, strict=True):
            target = next(
                (
                    existing
                    for existing_vector, existing in merged
                    if existing.label.casefold() == concept.label.casefold()
                    or _cosine(vector, existing_vector) >= DEDUP_SIMILARITY_THRESHOLD
                ),
                None,
            )
            acronyms = {a.acronym.strip(): a.expansion.strip() for a in concept.acronyms if a.acronym.strip()}
            if target is None:
                merged.append(
                    (
                        vector,
                        Concept(
                            id=f"c{len(merged) + 1}",
                            label=concept.label,
                            summary=concept.summary,
                            source_chunks=list(concept.source_chunks),
                            acronyms=acronyms,
                            examples=list(concept.examples),
                        ),
                    )
                )
                continue
            target.source_chunks = sorted(set(target.source_chunks) | set(concept.source_chunks))
            target.acronyms = {**acronyms, **target.acronyms}
            known = {example.label.casefold() for example in target.examples}
            for example in concept.examples:
                if len(target.examples) < MAX_EXAMPLES_PER_CONCEPT and example.label.casefold() not in known:
                    target.examples.append(example)
                    known.add(example.label.casefold())

        logger.info("Consolidated %d extracted concepts into %d.", len(extracted), len(merged))
        return [concept for _, concept in merged]

    # ---- Reduce 2: hierarchical selection + organization --------------------------------

    async def _select_group(self, group: Sequence[Concept], limit: int) -> list[Concept]:
        ids = {concept.id for concept in group}

        def validate(output: ConceptSelection) -> tuple[ConceptSelection, list[str]]:
            unknown = [cid for cid in output.concept_ids if cid not in ids]
            chosen = list(dict.fromkeys(cid for cid in output.concept_ids if cid in ids))[:limit]
            problems = [f"os identificadores {unknown} não estão na lista."] if unknown else []
            if not chosen:
                problems.append("escolha pelo menos um conceito.")
            return ConceptSelection(concept_ids=chosen), problems

        result = await generate_structured(
            self._llm,
            prompts.SELECTION_SYSTEM_PROMPT,
            prompts.build_selection_prompt(_preview(group), limit),
            ConceptSelection,
            validate,
        )
        chosen = set(result.concept_ids)
        return [concept for concept in group if concept.id in chosen]

    async def select(self, concepts: list[Concept]) -> list[Concept]:
        """Reduce the list by groups until it fits the organization prompt."""
        while len(concepts) > MAX_ORGANIZATION_CONCEPTS:
            group_count = math.ceil(len(concepts) / MAX_ORGANIZATION_CONCEPTS)
            group_size = math.ceil(len(concepts) / group_count)
            limit = max(3, MAX_ORGANIZATION_CONCEPTS // group_count)
            selected: list[Concept] = []
            for start in range(0, len(concepts), group_size):
                selected.extend(
                    await self._select_group(concepts[start : start + group_size], limit)
                )
            logger.info("Hierarchical selection reduced %d concepts to %d.", len(concepts), len(selected))
            if len(selected) >= len(concepts):
                break
            concepts = selected
        return concepts

    async def organize(self, concepts: Sequence[Concept]) -> MapOrganization:
        by_id = {concept.id: concept for concept in concepts}
        min_axes = min(MIN_TOPICS, len(concepts))

        def validate(output: MapOrganization) -> tuple[MapOrganization, list[str]]:
            problems: list[str] = []
            if not clean_concept_label(output.topic):
                problems.append("o campo topic está vazio.")
            if not output.synthesis.strip():
                problems.append("o campo synthesis está vazio.")
            if not min_axes <= len(output.axes) <= MAX_TOPICS:
                problems.append(f"crie de {min_axes} a {MAX_TOPICS} eixos (você criou {len(output.axes)}).")
            used: set[str] = set()
            axes = []
            for position, axis in enumerate(output.axes, start=1):
                title = clean_concept_label(axis.title)
                if not title:
                    problems.append(f"eixo {position}: o campo title está vazio.")
                if not axis.concepts:
                    problems.append(f"eixo {position}: inclua pelo menos um conceito.")
                for item in axis.concepts:
                    if item.id not in by_id:
                        problems.append(f"eixo {position}: o conceito {item.id} não está na lista.")
                    elif item.id in used:
                        problems.append(f"o conceito {item.id} aparece em mais de um eixo.")
                    elif by_id[item.id].label.casefold() == title.casefold():
                        problems.append(
                            f"eixo {position}: o título é igual ao conceito {item.id}; use um título que agrupe os conceitos."
                        )
                    used.add(item.id)
                axes.append(
                    axis.model_copy(
                        update={"title": title, "concepts": axis.concepts[:MAX_CONCEPTS_PER_TOPIC]}
                    )
                )
            return output.model_copy(update={"axes": axes}), problems

        system_prompt = prompts.ORGANIZATION_SYSTEM_PROMPT.format(
            min_axes=min_axes,
            max_axes=MAX_TOPICS,
            max_concepts_per_axis=MAX_CONCEPTS_PER_TOPIC,
        )
        return await generate_structured(
            self._llm,
            system_prompt,
            prompts.build_organization_prompt(_preview(concepts)),
            MapOrganization,
            validate,
        )

    # ---- Compile -----------------------------------------------------------------------

    @staticmethod
    def compile_graph(
        organization: MapOrganization,
        concepts: Sequence[Concept],
        fallback_topic: str,
    ) -> MindMapGraph:
        """Deterministically turn the organization into the React Flow tree contract."""
        by_id = {concept.id: concept for concept in concepts}
        topic = clean_concept_label(organization.topic) or fallback_topic
        nodes: list[MindMapNode] = []
        edges: list[MindMapEdge] = []

        def connect(source: str, target: str, relation: str) -> None:
            edges.append(
                MindMapEdge(
                    id=f"edge-{source}-{target}",
                    source=source,
                    target=target,
                    relation=relation,  # type: ignore[arg-type]
                    label=RELATION_LABELS[relation],
                )
            )

        all_chunks: set[int] = set()
        for order, axis in enumerate(organization.axes, start=1):
            topic_id = f"node-topic-{order}"
            axis_chunks: set[int] = set()
            for item in axis.concepts:
                concept = by_id[item.id]
                concept_id = f"node-concept-{concept.id}"
                axis_chunks.update(concept.source_chunks)
                nodes.append(
                    MindMapNode(
                        id=concept_id,
                        data=MindMapNodeData(
                            label=concept.label,
                            summary=concept.summary[:SUMMARY_MAX_CHARS],
                            category="concept",
                            acronyms=concept.acronyms,
                            source_chunks=concept.source_chunks,
                        ),
                    )
                )
                connect(topic_id, concept_id, item.relation)
                for position, example in enumerate(concept.examples, start=1):
                    example_id = f"node-example-{concept.id}-{position}"
                    nodes.append(
                        MindMapNode(
                            id=example_id,
                            data=MindMapNodeData(
                                label=example.label,
                                summary=example.summary[:SUMMARY_MAX_CHARS],
                                category="example",
                                source_chunks=concept.source_chunks,
                            ),
                        )
                    )
                    connect(concept_id, example_id, "exemplified_by")
            all_chunks.update(axis_chunks)
            nodes.append(
                MindMapNode(
                    id=topic_id,
                    data=MindMapNodeData(
                        label=axis.title,
                        summary=axis.summary.strip()[:SUMMARY_MAX_CHARS],
                        category="topic",
                        order=order,
                        source_chunks=sorted(axis_chunks),
                    ),
                )
            )
            connect("node-root", topic_id, "has_part")

        root = MindMapNode(
            id="node-root",
            type="input",
            data=MindMapNodeData(
                label=topic,
                summary=organization.synthesis.strip()[:SUMMARY_MAX_CHARS],
                category="root",
                source_chunks=sorted(all_chunks),
            ),
        )
        return MindMapGraph(topic=topic, nodes=[root, *nodes], edges=edges)

    async def build_graph(
        self,
        extracted: Sequence[ExtractedConcept],
        fallback_topic: str,
        valid_chunk_indices: set[int],
        on_phase: PhaseCallback | None = None,
    ) -> MindMapGraph:
        """Reduce the Map results of every section into a validated mind map."""
        if on_phase:
            await on_phase("consolidating")
        concepts = await self.consolidate(extracted)
        if not concepts:
            raise MindMapGenerationError("No study concepts were found in the material.")

        if on_phase:
            await on_phase("organizing")
        concepts = await self.select(concepts)
        organization = await self.organize(concepts)
        graph = self.compile_graph(organization, concepts, fallback_topic)

        errors = validate_mind_map_graph(graph, valid_chunk_indices)
        if errors:
            raise MindMapGenerationError("Invalid mind map: " + "; ".join(errors))
        return graph
