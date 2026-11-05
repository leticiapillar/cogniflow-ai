from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.sanitizer import sanitize_text_input

NOT_FOUND_ANSWER = "Não encontrei isso no material da aula."
MAX_HISTORY_TURNS = 8  # the last 4 exchanges (student + tutor)


class ChatTurn(BaseModel):
    """A previous message of the study session."""

    role: Literal["student", "tutor"]
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, value: str) -> str:
        # The client sends the whole history, so tutor turns are untrusted too.
        return sanitize_text_input(value, reject_on_injection=True)


class AskRequest(BaseModel):
    """Contract for `POST /api/documents/{document_id}/ask`."""

    question: str = Field(..., min_length=3, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    node_id: str | None = Field(
        default=None,
        max_length=100,
        description="Mind map node the question is about ('Tirar dúvida sobre este conceito').",
    )

    @field_validator("question")
    @classmethod
    def sanitize_question(cls, value: str) -> str:
        return sanitize_text_input(value, reject_on_injection=True)


class Citation(BaseModel):
    chunk_index: int = Field(..., ge=0)
    page_start: int = Field(..., ge=1)
    page_end: int = Field(..., ge=1)
    section_title: str | None = None
    excerpt: str = Field(..., description="Short passage of the chunk, for the student to check.")


class Term(BaseModel):
    term: str
    definition: str


class RelatedConcept(BaseModel):
    node_id: str
    label: str


class AskResponse(BaseModel):
    """Always the same structure: direct answer -> key points -> example -> terms -> sources."""

    found_in_material: bool
    answer: str = Field(..., description="Direct answer in 1-2 short sentences.")
    key_points: list[str] = Field(default_factory=list, description="Up to 3 short points.")
    example: str | None = Field(default=None, description="One example taken from the material.")
    terms: list[Term] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    related_concepts: list[RelatedConcept] = Field(
        default_factory=list,
        description="When nothing was found: up to 2 concepts of the mind map to explore.",
    )
