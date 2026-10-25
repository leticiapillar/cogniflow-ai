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
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[str] = []
    for section in sections:
        if len(section) <= chunk_size:
            chunks.append(section)
        else:
            sub_chunks = recursive_splitter.split_text(section)
            chunks.extend(chunk.strip() for chunk in sub_chunks if chunk.strip())

    logger.info(
        "Split text (%d chars) into %d semantic chunks (size=%d, overlap=%d).",
        len(text),
        len(chunks),
        chunk_size,
        chunk_overlap,
    )
    return chunks

