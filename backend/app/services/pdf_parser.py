from dataclasses import dataclass
import io
import logging
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger("cogniflow.services.pdf_parser")


class PDFParsingError(ValueError):
    """Raised when a PDF file cannot be parsed or contains no extractable text."""


@dataclass(frozen=True)
class PdfPage:
    """Extracted text of one PDF page with its 1-based page number."""

    number: int
    text: str


@dataclass(frozen=True)
class ParsedPdf:
    """Pages that contain text, plus the total page count of the document."""

    pages: list[PdfPage]
    page_count: int


def _normalize_extracted_page_text(raw_text: str) -> str:
    """Clean word-per-line artifacts and private-use glyphs common in exported PDFs."""
    text = raw_text.replace("", "(").replace("", ")")
    text = re.sub(r"\n[ \t]+\n", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_pdf(file_bytes: bytes) -> ParsedPdf:
    """Parse a PDF byte stream, keeping the page number of every non-empty page."""
    if not file_bytes or not file_bytes.lstrip().startswith(b"%PDF"):
        raise PDFParsingError("Invalid file format: byte stream is not a valid PDF.")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        page_count = len(reader.pages)
        pages: list[PdfPage] = []
        for index, page in enumerate(reader.pages):
            extracted = _normalize_extracted_page_text(page.extract_text() or "")
            if extracted:
                pages.append(PdfPage(number=index + 1, text=extracted))
            else:
                logger.debug("Page %d contained no extractable text.", index + 1)
    except (PdfReadError, Exception) as exc:
        logger.error("Failed to parse PDF document: %s", exc)
        raise PDFParsingError(f"Failed to read PDF document: {exc}") from exc

    if not pages:
        raise PDFParsingError("No extractable text found in the PDF document.")

    return ParsedPdf(pages=pages, page_count=page_count)


def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    """Extract and join text from all pages of a PDF byte stream."""
    parsed = parse_pdf(file_bytes)
    full_text = "\n\n".join(page.text for page in parsed.pages)
    logger.info(
        "Extracted %d characters from %d PDF pages.", len(full_text), len(parsed.pages)
    )
    return full_text
