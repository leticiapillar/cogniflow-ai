from bisect import bisect_right
from dataclasses import dataclass
import logging
import re
from typing import Sequence

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.pdf_parser import PdfPage

logger = logging.getLogger("cogniflow.services.chunking")

ACADEMIC_SECTION_HEADERS_REGEX = re.compile(
    r"(?m)^(?P<header>(?:#{1,4}\s+.+)|(?:\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ú][^\n]{2,80})|(?:[A-ZÀ-Ú][A-ZÀ-Ú\s]{4,60}:?))$"
)
MARKDOWN_HEADING_LINE_REGEX = re.compile(r"(?m)^[ \t]*(?P<hashes>#{1,4})[ \t]+(?P<title>\S.*)$")
PAGE_SEPARATOR = "\n\n"
SPLIT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


@dataclass(frozen=True)
class TextChunk:
    """A chunk of document text with the section and page range it came from."""

    content: str
    section_title: str | None
    page_start: int
    page_end: int


@dataclass(frozen=True)
class _Section:
    start: int
    end: int
    header_line: str | None
    title: str | None


def normalize_section_headers(text: str) -> str:
    """Turn numbered and upper-case academic headings into Markdown '##' headings."""
    return ACADEMIC_SECTION_HEADERS_REGEX.sub(
        lambda m: (
            m.group("header")
            if m.group("header").lstrip().startswith("#")
            else f"## {m.group('header').strip()}"
        ),
        text,
    )


def _find_sections(text: str) -> list[_Section]:
    """Split Markdown-normalized text at heading lines, keeping character offsets."""
    headings = list(MARKDOWN_HEADING_LINE_REGEX.finditer(text))
    boundaries = [0] + [match.start() for match in headings] + [len(text)]
    heading_at = {match.start(): match for match in headings}

    sections: list[_Section] = []
    for start, end in zip(boundaries, boundaries[1:]):
        if start >= end or not text[start:end].strip():
            continue
        heading = heading_at.get(start)
        sections.append(
            _Section(
                start=start,
                end=end,
                header_line=(
                    f"{heading.group('hashes')} {heading.group('title').strip()}"
                    if heading
                    else None
                ),
                title=heading.group("title").strip() if heading else None,
            )
        )
    return sections


def _split_section(
    text: str,
    section: _Section,
    chunk_size: int,
    chunk_overlap: int,
) -> list[tuple[str, int, int]]:
    """Return (content, start_offset, end_offset) for the chunks of one section."""
    section_text = text[section.start : section.end]
    stripped = section_text.strip()
    if len(stripped) <= chunk_size:
        leading = len(section_text) - len(section_text.lstrip())
        start = section.start + leading
        return [(stripped, start, start + len(stripped))]

    header_prefix = f"{section.header_line}\n" if section.header_line else ""
    effective_chunk_size = chunk_size
    if header_prefix and len(header_prefix) < chunk_size // 2:
        effective_chunk_size = max(chunk_overlap + 50, chunk_size - len(header_prefix))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=effective_chunk_size,
        chunk_overlap=min(chunk_overlap, effective_chunk_size - 20),
        separators=SPLIT_SEPARATORS,
        add_start_index=True,
    )
    pieces: list[tuple[str, int, int]] = []
    for document in splitter.create_documents([section_text]):
        cleaned = document.page_content.strip()
        if not cleaned:
            continue
        start = section.start + int(document.metadata["start_index"])
        end = start + len(document.page_content)
        if (
            section.header_line
            and not cleaned.startswith(section.header_line)
            and len(header_prefix) + len(cleaned) <= chunk_size + 50
        ):
            cleaned = f"{header_prefix}{cleaned}"
        pieces.append((cleaned, start, end))
    return pieces


def chunk_pages(
    pages: Sequence[PdfPage],
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[TextChunk]:
    """Chunk document pages by section headings, then by size with overlap, tracking pages."""
    page_starts: list[int] = []
    normalized_pages: list[str] = []
    offset = 0
    for page in pages:
        normalized = normalize_section_headers(page.text)
        page_starts.append(offset)
        normalized_pages.append(normalized)
        offset += len(normalized) + len(PAGE_SEPARATOR)
    text = PAGE_SEPARATOR.join(normalized_pages)

    def page_number_at(char_offset: int) -> int:
        return pages[max(0, bisect_right(page_starts, char_offset) - 1)].number

    chunks: list[TextChunk] = []
    for section in _find_sections(text):
        for content, start, end in _split_section(text, section, chunk_size, chunk_overlap):
            chunks.append(
                TextChunk(
                    content=content,
                    section_title=section.title,
                    page_start=page_number_at(start),
                    page_end=page_number_at(max(start, end - 1)),
                )
            )

    logger.info(
        "Split %d pages (%d chars) into %d semantic chunks (size=%d, overlap=%d).",
        len(pages),
        len(text),
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks


def split_text_by_headers(text: str) -> list[str]:
    """Split structured or academic text into semantic sections based on headings."""
    if not text or not text.strip():
        return []
    normalized = normalize_section_headers(text)
    sections = [normalized[s.start : s.end].strip() for s in _find_sections(normalized)]
    return sections or [text.strip()]


def chunk_text_semantically(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[str]:
    """Chunk a single block of text (treated as one page) and return the chunk contents."""
    if not text or not text.strip():
        return []
    chunks = chunk_pages([PdfPage(number=1, text=text)], chunk_size, chunk_overlap)
    return [chunk.content for chunk in chunks]
