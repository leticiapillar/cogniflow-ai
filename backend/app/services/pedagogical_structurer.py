from dataclasses import dataclass, field
import json
import re
from typing import Any, Sequence

ABBREVIATION_PROTECT_REGEX = re.compile(
    r"\b(Prof|Dr|Dra|Sr|Sra|Me|Ma|Esp|Ex|Fig|Cap|Art|Inc|Ltd|et al|vs|p\.ex|i\.e|e\.g)\.",
    re.IGNORECASE,
)
AUTHOR_OR_METADATA_LINE_REGEX = re.compile(
    r"^\s*(?:Prof\.?\s*Dr\.?|Autor(?:a|es)?\s*:|Referências\s*:|Fonte\s*:|Página\s+\d+|\d+\s*$)",
    re.IGNORECASE,
)
DANGLING_TAIL_WORDS = frozenset(
    {
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "uns",
        "umas",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "em",
        "na",
        "no",
        "nas",
        "nos",
        "por",
        "pelo",
        "pela",
        "para",
        "com",
        "sem",
        "sob",
        "sobre",
        "entre",
        "que",
        "se",
        "ou",
        "e",
        "nem",
        "mas",
        "como",
        "seu",
        "sua",
        "seus",
        "suas",
        "mais",
        "muito",
        "ao",
        "aos",
        "à",
        "às",
        "the",
        "an",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "and",
        "or",
        "but",
        "as",
        "into",
        "its",
        "their",
    }
)
PORTUGUESE_INDICATORS = frozenset(
    {
        "que",
        "como",
        "para",
        "com",
        "uma",
        "dos",
        "das",
        "pela",
        "pelo",
        "são",
        "não",
        "está",
        "evolução",
        "definição",
        "fundamentos",
        "conceito",
        "inteligência",
        "arquitetura",
    }
)
HEADING_LINE_REGEX = re.compile(
    r"^\s*(?:(?P<hashes>#{1,4})\s+(?P<md>.+)|(?P<num>\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ú][^\n]{2,80}))$"
)
YEAR_MILESTONE_REGEX = re.compile(r"\b(19\d{2}|20\d{2}\+?)\b")
JSON_OBJECT_EXTRACT_REGEX = re.compile(r"\{[\s\S]*\}")


@dataclass
class PedagogicalConceptItem:
    """Represents a specific Level-2 concept, comparison, milestone, or example."""

    label: str
    summary: str
    category: str = "concept"
    edge_label: str = "abrange"


@dataclass
class PedagogicalThematicAxis:
    """Represents a Level-1 thematic pillar organizing related concepts."""

    title: str
    summary: str
    edge_label: str = "estrutura-se em"
    concepts: list[PedagogicalConceptItem] = field(default_factory=list)


@dataclass
class PedagogicalOutline:
    """Intermediate structured pedagogical representation (Synthesis + Concept Tree)."""

    topic: str
    language: str
    direct_synthesis: str
    axes: list[PedagogicalThematicAxis] = field(default_factory=list)


def detect_language(query: str, context_chunks: Sequence[str]) -> str:
    """Detect whether the output should be in Portuguese ('pt') or English ('en')."""
    sample_text = f"{query} " + " ".join(context_chunks[:2])
    tokens = {
        tok.lower() for tok in re.findall(r"[a-zA-ZÀ-ÿ]{2,}", sample_text)
    }
    if tokens & PORTUGUESE_INDICATORS or any(
        ch in query.lower() for ch in "ãõçáéíóúâêô"
    ):
        return "pt"
    return "en"


def reflow_pdf_text_into_sentences(raw_chunk: str) -> list[tuple[str | None, str]]:
    """Reflow wrapped PDF lines into complete sentences while preserving section headers."""
    lines = [line.strip() for line in raw_chunk.splitlines() if line.strip()]
    if not lines:
        return []

    current_header: str | None = None
    paragraphs: list[tuple[str | None, str]] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if buffer:
            joined = " ".join(buffer)
            joined = re.sub(r"\s+", " ", joined).strip()
            if joined:
                paragraphs.append((current_header, joined))
            buffer.clear()

    for raw_line in lines:
        cleaned_line = raw_line.strip(" \t●*-")
        if not cleaned_line:
            continue

        if AUTHOR_OR_METADATA_LINE_REGEX.match(cleaned_line):
            continue

        heading_match = HEADING_LINE_REGEX.match(raw_line)
        if heading_match:
            flush_buffer()
            hashes = heading_match.group("hashes") or ""
            raw_title = (
                heading_match.group("md") or heading_match.group("num") or ""
            ).strip(" #*:-")
            # Ignore single-# document title if it's just the top document banner; keep ##+ or numbered sections
            if raw_title and len(raw_title) <= 90 and hashes != "#":
                current_header = raw_title
            continue

        colon_parts = cleaned_line.split(":", 1)
        if (
            len(colon_parts) == 2
            and 1 <= len(colon_parts[0].split()) <= 6
            and len(colon_parts[1].strip()) >= 10
            and not buffer
        ):
            paragraphs.append((current_header, cleaned_line))
            continue

        buffer.append(cleaned_line)
        if cleaned_line.endswith((".", "!", "?", ";")):
            if not ABBREVIATION_PROTECT_REGEX.search(cleaned_line[-8:]):
                flush_buffer()

    flush_buffer()

    sentences: list[tuple[str | None, str]] = []
    for header, paragraph in paragraphs:
        protected = ABBREVIATION_PROTECT_REGEX.sub(
            lambda m: m.group(0).replace(".", "<DOT>"), paragraph
        )
        parts = [
            s.replace("<DOT>", ".").strip()
            for s in re.split(r"(?<=[.!?])\s+", protected)
            if s.strip()
        ]
        for part in parts:
            if len(part) >= 12 and not AUTHOR_OR_METADATA_LINE_REGEX.match(part):
                sentences.append((header, part))
    return sentences


def clean_concept_label(raw_label: str, max_words: int = 6) -> str:
    """Clean and trim a concept label so it never ends with dangling prepositions or unmatched parens."""
    text = raw_label.strip(" #\t●*-.,;:")
    text = re.sub(
        r"^(?:A\s+discussão\s+sobre\s+a\s+|No\s+contexto\s+mais\s+amplo\s+dos?\s+seus?\s+|Compreender\s+a\s+natureza\s+e\s+o\s+|Sua\s+capacidade\s+de\s+)",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    words = text.split()
    if len(words) > max_words:
        words = words[:max_words]

    while words and words[-1].lower().strip(".,;:()[]") in DANGLING_TAIL_WORDS:
        words.pop()

    result = " ".join(words).strip(" .,;:-")
    if "(" in result and ")" not in result:
        before_paren = result.split("(", 1)[0].strip()
        if len(before_paren) >= 3:
            result = before_paren
        else:
            result = result.replace("(", "").strip()

    final_words = result.split()
    while (
        final_words
        and final_words[-1].lower().strip(".,;:()[]") in DANGLING_TAIL_WORDS
    ):
        final_words.pop()
    result = " ".join(final_words).strip(" .,;:-")

    if result:
        result = result[0].upper() + result[1:]
    return result[:180]


def derive_concept_from_sentence(
    sentence: str, language: str = "pt"
) -> PedagogicalConceptItem | None:
    """Extract a pedagogical (label, summary, category, edge_label) from a clean sentence."""
    colon_parts = sentence.split(":", 1)
    if (
        len(colon_parts) == 2
        and 1 <= len(colon_parts[0].split()) <= 7
        and len(colon_parts[1].strip()) >= 5
    ):
        raw_label = colon_parts[0].strip()
        summary = colon_parts[1].strip()
        label = clean_concept_label(raw_label, max_words=7) or raw_label[:80]
    else:
        year_match = YEAR_MILESTONE_REGEX.search(sentence)
        if year_match and len(sentence.split()) > 6:
            year_str = year_match.group(1)
            after_year = sentence[year_match.end() :].strip(" ,:-—()")
            key_phrase = clean_concept_label(after_year, max_words=4)
            label = f"{year_str}: {key_phrase}" if key_phrase else f"Marco {year_str}"
            summary = sentence
        else:
            verb_split = re.split(
                r"\b(?:é\s+um(?:a)?|são\s+|refere-se\s+a|destaca-se\s+pela|consiste\s+em|define-se\s+como|baseia-se\s+em|is\s+a(?:n)?|refers\s+to|consists\s+of)\b",
                sentence,
                maxsplit=1,
                flags=re.IGNORECASE,
            )
            if len(verb_split) == 2 and 1 <= len(verb_split[0].split()) <= 7:
                label = clean_concept_label(verb_split[0], max_words=6)
                summary = sentence
            else:
                label = clean_concept_label(sentence, max_words=5)
                summary = sentence

    if len(label) < 3 or label.lower() in DANGLING_TAIL_WORDS:
        return None

    lower_sent = sentence.lower()
    is_example = any(
        kw in lower_sent
        for kw in ("ex:", "exemplo", "como chatgpt", "dall-e", "such as", "example")
    )
    is_milestone = bool(YEAR_MILESTONE_REGEX.search(sentence))

    if language == "pt":
        if is_example:
            edge_label = "exemplificado por"
            category = "example"
        elif is_milestone:
            edge_label = "evoluiu em"
            category = "concept"
        elif any(
            w in lower_sent for w in ("diferen", "tradicional", "distin", "contraste")
        ):
            edge_label = "diferencia-se por"
            category = "concept"
        else:
            edge_label = "abrange"
            category = "concept"
    else:
        if is_example:
            edge_label = "exemplified by"
            category = "example"
        elif is_milestone:
            edge_label = "evolved into"
            category = "concept"
        else:
            edge_label = "encompasses"
            category = "concept"

    return PedagogicalConceptItem(
        label=label,
        summary=summary[:800],
        category=category,
        edge_label=edge_label,
    )


def _classify_thematic_axis(
    header: str | None, sentence: str, language: str
) -> tuple[str, str, str]:
    """Classify a concept into a high-level pedagogical axis (title, summary, edge_label)."""
    if header and len(header) >= 4:
        clean_hdr = clean_concept_label(header, max_words=6)
        if clean_hdr and len(clean_hdr) >= 4:
            return (
                clean_hdr,
                (
                    f"Eixo temático estruturante sobre {clean_hdr}."
                    if language == "pt"
                    else f"Core thematic section covering {clean_hdr}."
                ),
                "estrutura-se em" if language == "pt" else "structures into",
            )

    lower = sentence.lower()
    if language == "pt":
        if YEAR_MILESTONE_REGEX.search(sentence) or any(
            k in lower
            for k in (
                "histór",
                "evolu",
                "surg",
                "década",
                "anos 50",
                "anos 60",
                "marco",
                "cronolog",
            )
        ):
            return (
                "Evolução Histórica",
                "Linha do tempo e marcos fundamentais do desenvolvimento da área.",
                "evoluiu em",
            )
        if any(
            k in lower
            for k in (
                "pilar",
                "arquitetura",
                "transformer",
                "modelo",
                "treinamento",
                "rede",
                "fundamento",
                "mecanismo",
                "pipeline",
                "banco",
                "validação",
            )
        ):
            return (
                "Fundamentos e Arquitetura",
                "Pilares técnicos, modelos e mecanismos de funcionamento.",
                "fundamenta-se em",
            )
        if any(
            k in lower
            for k in (
                "ex:",
                "exemplo",
                "aplicac",
                "conteúdo",
                "imagem",
                "áudio",
                "código",
                "ética",
                "chatgpt",
            )
        ):
            return (
                "Aplicações e Conteúdos",
                "Modalidades geradas, exemplos práticos e impactos de uso.",
                "aplica-se em",
            )
        return (
            "Definição e Distinção",
            "Conceitos essenciais, características e diferenciação conceitual.",
            "define-se por",
        )
    else:
        if YEAR_MILESTONE_REGEX.search(sentence) or any(
            k in lower for k in ("histor", "evolu", "timeline", "milestone")
        ):
            return (
                "Historical Evolution",
                "Chronological milestones and key developments.",
                "evolved through",
            )
        if any(
            k in lower
            for k in (
                "architecture",
                "pillar",
                "model",
                "mechanism",
                "foundation",
                "algorithm",
                "protocol",
                "structure",
                "system",
            )
        ):
            return (
                "Core Foundations",
                "Technical mechanisms, architectures, and structural principles.",
                "grounded in",
            )
        return (
            "Key Concepts & Definitions",
            "Essential definitions and domain relationships extracted from the material.",
            "structures into",
        )


def build_pedagogical_outline(
    query: str,
    context_chunks: Sequence[str],
    max_concepts: int = 12,
) -> PedagogicalOutline:
    """Step 1 (Synthesize) + Step 2 (Structure): build a pedagogical outline from RAG chunks."""
    language = detect_language(query, context_chunks)
    if not context_chunks:
        fallback_synth = (
            f"Visão geral estruturada sobre {query}."
            if language == "pt"
            else f"Structured overview of {query}."
        )
        return PedagogicalOutline(
            topic=query,
            language=language,
            direct_synthesis=fallback_synth,
            axes=[
                PedagogicalThematicAxis(
                    title=(
                        f"Visão Geral: {query[:50]}"
                        if language == "pt"
                        else f"Overview: {query[:50]}"
                    ),
                    summary=fallback_synth,
                    edge_label="explora" if language == "pt" else "explores",
                )
            ],
        )

    all_sentences: list[tuple[str | None, str]] = []
    for chunk in context_chunks:
        all_sentences.extend(reflow_pdf_text_into_sentences(chunk))

    seen_labels: set[str] = set()
    axes_map: dict[str, PedagogicalThematicAxis] = {}
    synthesis_sentences: list[str] = []

    for header, sentence in all_sentences:
        concept = derive_concept_from_sentence(sentence, language=language)
        if concept is None:
            continue
        norm_label = concept.label.lower()
        if norm_label in seen_labels or norm_label == query.strip().lower():
            continue
        seen_labels.add(norm_label)

        if len(synthesis_sentences) < 3:
            synthesis_sentences.append(
                f"{concept.label}: {concept.summary}"
                if not concept.summary.lower().startswith(norm_label)
                else concept.summary
            )

        axis_title, axis_summary, axis_edge = _classify_thematic_axis(
            header, sentence, language
        )
        if axis_title not in axes_map:
            axes_map[axis_title] = PedagogicalThematicAxis(
                title=axis_title,
                summary=axis_summary,
                edge_label=axis_edge,
            )
        axes_map[axis_title].concepts.append(concept)

        total_concepts = sum(len(ax.concepts) for ax in axes_map.values())
        if total_concepts >= max_concepts:
            break

    # If all concepts landed in a single axis and there are >= 4 concepts, split into balanced pillars
    axes_list = list(axes_map.values())
    if len(axes_list) == 1 and len(axes_list[0].concepts) >= 4:
        all_items = axes_list[0].concepts
        pillar_size = 2 if len(all_items) <= 5 else 3
        split_axes: list[PedagogicalThematicAxis] = []
        for idx, start in enumerate(range(0, len(all_items), pillar_size), start=1):
            group = all_items[start : start + pillar_size]
            if not group:
                continue
            head = group[0]
            split_axes.append(
                PedagogicalThematicAxis(
                    title=head.label,
                    summary=head.summary,
                    edge_label=(
                        "estrutura-se em" if language == "pt" else "structures into"
                    ),
                    concepts=group[1:],
                )
            )
        axes_list = split_axes

    if not axes_list:
        first_excerpt = re.sub(r"\s+", " ", context_chunks[0]).strip()[:300]
        default_title = (
            "Conceitos Principais" if language == "pt" else "Core Material Concepts"
        )
        axes_list = [
            PedagogicalThematicAxis(
                title=default_title,
                summary=first_excerpt,
                edge_label="abrange" if language == "pt" else "encompasses",
            )
        ]

    direct_synthesis = (
        " ".join(synthesis_sentences)[:750]
        if synthesis_sentences
        else re.sub(r"\s+", " ", context_chunks[0]).strip()[:400]
    )

    return PedagogicalOutline(
        topic=query,
        language=language,
        direct_synthesis=direct_synthesis,
        axes=axes_list,
    )


def format_pedagogical_outline_for_prompt(outline: PedagogicalOutline) -> str:
    """Render the intermediate pedagogical outline as structured guidance for the LLM prompt."""
    lines = [
        f"Direct Synthesis Answering the Query: {outline.direct_synthesis}",
        "Extracted Thematic Axes & Key Facts:",
    ]
    for idx, axis in enumerate(outline.axes, start=1):
        lines.append(f"  Axis {idx}: {axis.title} (relation: '{axis.edge_label}') — {axis.summary[:160]}")
        for concept in axis.concepts[:6]:
            lines.append(
                f"    - [{concept.category}] {concept.label} (relation: '{concept.edge_label}'): {concept.summary[:200]}"
            )
    return "\n".join(lines)


def compile_outline_to_mind_map_dict(outline: PedagogicalOutline) -> dict[str, object]:
    """Deterministically compile a PedagogicalOutline into the strict React Flow JSON contract."""
    root_id = "node-root"
    nodes: list[dict[str, object]] = [
        {
            "id": root_id,
            "type": "input",
            "data": {
                "label": outline.topic[:200],
                "summary": outline.direct_synthesis[:900],
                "category": "root",
            },
            "position": {"x": 0.0, "y": 0.0},
        }
    ]
    edges: list[dict[str, object]] = []

    concept_counter = 1
    for axis_idx, axis in enumerate(outline.axes, start=1):
        topic_id = f"node-topic-{axis_idx}"
        nodes.append(
            {
                "id": topic_id,
                "type": "default",
                "data": {
                    "label": axis.title[:180],
                    "summary": axis.summary[:800],
                    "category": "topic",
                },
                "position": {"x": float((axis_idx - 1) * 280), "y": 140.0},
            }
        )
        edges.append(
            {
                "id": f"edge-root-topic-{axis_idx}",
                "source": root_id,
                "target": topic_id,
                "label": axis.edge_label,
                "animated": False,
            }
        )

        for concept in axis.concepts:
            if concept.label.lower() == axis.title.lower():
                continue
            concept_id = f"node-{concept_counter}"
            concept_counter += 1
            nodes.append(
                {
                    "id": concept_id,
                    "type": "default",
                    "data": {
                        "label": concept.label[:180],
                        "summary": concept.summary[:800],
                        "category": concept.category,
                    },
                    "position": {
                        "x": float((axis_idx - 1) * 280),
                        "y": 280.0,
                    },
                }
            )
            edges.append(
                {
                    "id": f"edge-topic-{axis_idx}-concept-{concept_counter - 1}",
                    "source": topic_id,
                    "target": concept_id,
                    "label": concept.edge_label,
                    "animated": False,
                }
            )

    return {
        "topic": outline.topic,
        "nodes": nodes,
        "edges": edges,
    }


def normalize_llm_mind_map_json(
    raw_output: str,
    query: str,
    context_chunks: Sequence[str],
) -> str:
    """Repair common LLM JSON quirks (nested children, missing positions/ids, or outline format)."""
    if not raw_output or not raw_output.strip():
        return raw_output

    text = raw_output.strip()
    if not text.startswith("{"):
        match = JSON_OBJECT_EXTRACT_REGEX.search(text)
        if match:
            text = match.group(0)

    try:
        parsed: dict[str, Any] = json.loads(text)
    except Exception:
        return raw_output

    if not isinstance(parsed, dict):
        return raw_output

    language = detect_language(query, context_chunks)
    default_edge_verb = "abrange" if language == "pt" else "encompasses"

    # Case 1: LLM returned an outline with "axes" / "branches" / "pillars" instead of "nodes"
    raw_branches = (
        parsed.get("axes")
        or parsed.get("branches")
        or parsed.get("pillars")
        or parsed.get("topics")
    )
    if isinstance(raw_branches, list) and not parsed.get("nodes"):
        axes: list[PedagogicalThematicAxis] = []
        for branch in raw_branches:
            if not isinstance(branch, dict):
                continue
            b_title = str(
                branch.get("title") or branch.get("label") or branch.get("name") or ""
            ).strip()
            if not b_title:
                continue
            b_summary = str(
                branch.get("summary") or branch.get("description") or b_title
            ).strip()
            b_edge = str(
                branch.get("edge_label")
                or branch.get("relation")
                or ("estrutura-se em" if language == "pt" else "structures into")
            ).strip()
            children_raw = (
                branch.get("concepts")
                or branch.get("children")
                or branch.get("subtopics")
                or branch.get("items")
                or []
            )
            concepts: list[PedagogicalConceptItem] = []
            if isinstance(children_raw, list):
                for child in children_raw:
                    if isinstance(child, dict):
                        c_label = str(
                            child.get("label")
                            or child.get("title")
                            or child.get("name")
                            or ""
                        ).strip()
                        if not c_label:
                            continue
                        c_summary = str(
                            child.get("summary")
                            or child.get("description")
                            or c_label
                        ).strip()
                        c_cat = str(child.get("category") or "concept").strip()
                        c_edge = str(
                            child.get("edge_label")
                            or child.get("relation")
                            or default_edge_verb
                        ).strip()
                        concepts.append(
                            PedagogicalConceptItem(
                                label=c_label,
                                summary=c_summary,
                                category=c_cat if c_cat in {"concept", "example", "topic"} else "concept",
                                edge_label=c_edge,
                            )
                        )
            axes.append(
                PedagogicalThematicAxis(
                    title=b_title,
                    summary=b_summary,
                    edge_label=b_edge,
                    concepts=concepts,
                )
            )
        if axes:
            synthesis = str(
                parsed.get("direct_synthesis")
                or parsed.get("synthesis")
                or parsed.get("summary")
                or f"Síntese sobre {query}."
            )
            compiled = compile_outline_to_mind_map_dict(
                PedagogicalOutline(
                    topic=query,
                    language=language,
                    direct_synthesis=synthesis,
                    axes=axes,
                )
            )
            return json.dumps(compiled, ensure_ascii=False)

    # Case 2: Standard {"nodes": [...], "edges": [...]} with possible missing defaults or nested children
    raw_nodes = parsed.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return raw_output

    normalized_nodes: list[dict[str, Any]] = []
    normalized_edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def walk_node(raw_node: dict[str, Any], parent_id: str | None = None, idx_hint: int = 1) -> None:
        node_id = str(raw_node.get("id") or f"node-{idx_hint}").strip()
        while node_id in seen_node_ids:
            idx_hint += 1
            node_id = f"{node_id}-{idx_hint}"
        seen_node_ids.add(node_id)

        raw_data = raw_node.get("data")
        if not isinstance(raw_data, dict):
            raw_data = {}

        label = str(
            raw_data.get("label")
            or raw_node.get("label")
            or raw_node.get("title")
            or f"Conceito {idx_hint}"
        ).strip()
        summary = str(
            raw_data.get("summary")
            or raw_node.get("summary")
            or raw_node.get("description")
            or label
        ).strip()
        category = str(
            raw_data.get("category")
            or raw_node.get("category")
            or ("root" if not normalized_nodes else "concept")
        ).strip().lower()
        if category not in {"root", "topic", "concept", "example"}:
            category = "root" if not normalized_nodes else "concept"

        node_type = str(raw_node.get("type") or ("input" if category == "root" else "default")).strip()
        if node_type not in {"input", "default", "output", "custom"}:
            node_type = "input" if category == "root" else "default"

        raw_pos = raw_node.get("position")
        if not isinstance(raw_pos, dict):
            raw_pos = {"x": 0.0, "y": 0.0}
        pos = {
            "x": float(raw_pos.get("x", 0.0) or 0.0),
            "y": float(raw_pos.get("y", 0.0) or 0.0),
        }

        normalized_nodes.append(
            {
                "id": node_id,
                "type": node_type,
                "data": {
                    "label": label[:200],
                    "summary": summary[:1000],
                    "category": category,
                },
                "position": pos,
            }
        )

        if parent_id is not None:
            rel_label = str(raw_node.get("edge_label") or raw_node.get("relation") or default_edge_verb).strip()
            normalized_edges.append(
                {
                    "id": f"edge-{parent_id}-{node_id}",
                    "source": parent_id,
                    "target": node_id,
                    "label": rel_label[:120],
                    "animated": False,
                }
            )

        children = raw_node.get("children") or raw_node.get("subtopics")
        if isinstance(children, list):
            for child_idx, child in enumerate(children, start=1):
                if isinstance(child, dict):
                    walk_node(child, parent_id=node_id, idx_hint=idx_hint * 10 + child_idx)

    for idx, item in enumerate(raw_nodes, start=1):
        if isinstance(item, dict):
            walk_node(item, parent_id=None, idx_hint=idx)

    raw_edges = parsed.get("edges")
    seen_edge_ids: set[str] = {e["id"] for e in normalized_edges}
    if isinstance(raw_edges, list):
        for edge_idx, raw_edge in enumerate(raw_edges, start=1):
            if not isinstance(raw_edge, dict):
                continue
            source = str(raw_edge.get("source") or "").strip()
            target = str(raw_edge.get("target") or "").strip()
            if (
                not source
                or not target
                or source == target
                or source not in seen_node_ids
                or target not in seen_node_ids
            ):
                continue
            edge_id = str(raw_edge.get("id") or f"edge-{source}-{target}-{edge_idx}").strip()
            while edge_id in seen_edge_ids:
                edge_idx += 1
                edge_id = f"{edge_id}-{edge_idx}"
            seen_edge_ids.add(edge_id)

            raw_label = raw_edge.get("label")
            label_str = str(raw_label).strip()[:120] if raw_label else default_edge_verb
            normalized_edges.append(
                {
                    "id": edge_id,
                    "source": source,
                    "target": target,
                    "label": label_str,
                    "animated": bool(raw_edge.get("animated", False)),
                }
            )

    synthesis_text = parsed.get("pedagogical_synthesis") or parsed.get("synthesis")
    if (
        isinstance(synthesis_text, str)
        and synthesis_text.strip()
        and normalized_nodes
    ):
        normalized_nodes[0]["data"]["summary"] = synthesis_text.strip()[:1000]

    result_payload = {
        "topic": query,
        "nodes": normalized_nodes,
        "edges": normalized_edges,
    }
    return json.dumps(result_payload, ensure_ascii=False)
