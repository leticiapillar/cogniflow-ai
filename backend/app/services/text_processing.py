"""Deterministic text clean-up around the AI steps.

Before the LLM: rejoin wrapped PDF lines into sentences and drop author/page metadata.
After the LLM: trim concept labels so they never end with a dangling preposition.
This module never generates pedagogical content itself.
"""

import re

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
HEADING_LINE_REGEX = re.compile(
    r"^\s*(?:(?P<hashes>#{1,4})\s+(?P<md>.+)|(?P<num>\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ú][^\n]{2,80}))$"
)


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


def prepare_chunk_text(content: str) -> str:
    """Readable text of a chunk for the LLM: reflowed sentences, without metadata lines."""
    sentences = [sentence for _, sentence in reflow_pdf_text_into_sentences(content)]
    return " ".join(sentences)
