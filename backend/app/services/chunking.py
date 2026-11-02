import logging
import re

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger("cogniflow.services.chunking")

ACADEMIC_SECTION_HEADERS_REGEX = re.compile(
    r"(?m)^(?P<header>(?:#{1,4}\s+.+)|(?:\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ú][^\n]{2,80})|(?:[A-ZÀ-Ú][A-ZÀ-Ú\s]{4,60}:?))$"
)
MARKDOWN_HEADING_LINE_REGEX = re.compile(r"^\s*(?P<hashes>#{1,4})\s+(?P<title>.+)$")


def _extract_section_header(section_text: str) -> str | None:
    """Extract the leading Markdown heading line from a section, if present."""
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        match = MARKDOWN_HEADING_LINE_REGEX.match(stripped)
        if match:
            return f"{match.group('hashes')} {match.group('title').strip()}"
        break
    return None


def split_text_by_headers(text: str) -> list[str]:
    """Split structured or academic text into semantic sections based on headings."""
    if not text or not text.strip():
        return []

    normalized_markdown = ACADEMIC_SECTION_HEADERS_REGEX.sub(
        lambda m: (
            m.group("header")
            if m.group("header").lstrip().startswith("#")
            else f"## {m.group('header').strip()}"
        ),
        text,
    )

    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False,
    )
    documents = markdown_splitter.split_text(normalized_markdown)
    sections = [doc.page_content.strip() for doc in documents if doc.page_content.strip()]
    return sections if sections else [text.strip()]


def chunk_text_semantically(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> list[str]:
    """Split text first by semantic headers and then by fixed-size recursive overlap."""
    sections = split_text_by_headers(text)
    separators = ["\n\n", "\n", ". ", " ", ""]

    chunks: list[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
            continue

        section_header = _extract_section_header(section)
        header_prefix = f"{section_header}\n" if section_header else ""
        effective_chunk_size = chunk_size
        if header_prefix and len(header_prefix) < chunk_size // 2:
            effective_chunk_size = max(
                chunk_overlap + 50, chunk_size - len(header_prefix)
            )

        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=effective_chunk_size,
            chunk_overlap=min(chunk_overlap, effective_chunk_size - 20),
            separators=separators,
        )
        sub_chunks = recursive_splitter.split_text(section)
        for sub_chunk in sub_chunks:
            cleaned = sub_chunk.strip()
            if not cleaned:
                continue
            if (
                section_header
                and not cleaned.startswith(section_header)
                and len(header_prefix) + len(cleaned) <= chunk_size + 50
            ):
                cleaned = f"{header_prefix}{cleaned}"
            chunks.append(cleaned)

    logger.info(
        "Split text (%d chars) into %d semantic chunks (size=%d, overlap=%d).",
        len(text),
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks

