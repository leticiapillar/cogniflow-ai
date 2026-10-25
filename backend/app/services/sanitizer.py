import logging
import re

logger = logging.getLogger("cogniflow.services.sanitizer")


class PromptInjectionError(ValueError):
    """Raised when anomalous prompt injection instructions are detected in user input."""


class InputValidationError(ValueError):
    """Raised when uploaded file metadata or payload fails validation."""


PROMPT_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(all\s+)?(previous|prior|above|preceding)\s+(instructions|prompts|rules)",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts|rules)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(system\s+override|developer\s+mode|jailbreak|you\s+are\s+now\s+dan\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(reveal|print|show|output)\s+(your|the)\s+(system\s+prompt|hidden\s+instructions)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>)",
        re.IGNORECASE,
    ),
    re.compile(
        r"forget\s+(everything|all\s+instructions)\s+(you\s+were\s+told|above)",
        re.IGNORECASE,
    ),
)

CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def detect_prompt_injection(text: str) -> str | None:
    """Inspect text and return the matched pattern description if prompt injection is found."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def sanitize_text_input(text: str, reject_on_injection: bool = True) -> str:
    """Sanitize input text by stripping control characters and blocking prompt injection."""
    if not text or not text.strip():
        raise InputValidationError("Input text cannot be empty.")

    cleaned = CONTROL_CHARS_REGEX.sub("", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    matched_injection = detect_prompt_injection(cleaned)
    if matched_injection:
        logger.warning(
            "Blocked potential prompt injection pattern: '%s'", matched_injection
        )
        if reject_on_injection:
            raise PromptInjectionError(
                f"Potential prompt injection detected and blocked: '{matched_injection}'."
            )
        for pattern in PROMPT_INJECTION_PATTERNS:
            cleaned = pattern.sub("[REDACTED_INSTRUCTION]", cleaned)

    return cleaned


def validate_pdf_upload(
    filename: str,
    content_type: str | None,
    file_bytes: bytes,
    max_size_bytes: int = 20 * 1024 * 1024,
) -> str:
    """Validate uploaded PDF filename, MIME type, and payload size."""
    if not filename or not filename.strip():
        raise InputValidationError("Uploaded file must have a valid filename.")

    safe_filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename.strip())
    if not safe_filename.lower().endswith(".pdf"):
        raise InputValidationError("Only '.pdf' files are accepted for ingestion.")

    if content_type and content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise InputValidationError(
            f"Unsupported content type '{content_type}'. Expected 'application/pdf'."
        )

    if not file_bytes:
        raise InputValidationError("Uploaded PDF file is empty.")

    if len(file_bytes) > max_size_bytes:
        raise InputValidationError(
            f"Uploaded PDF exceeds maximum allowed size of {max_size_bytes} bytes."
        )

    return safe_filename

