"""Shapes the LLM must answer with in the tutor. Sent as Ollama's `format`."""

from pydantic import BaseModel, Field


class StandaloneQuestion(BaseModel):
    question: str = Field(
        ..., description="A pergunta reescrita de forma completa, sem depender da conversa."
    )


class TutorTerm(BaseModel):
    term: str = Field(..., description="Termo técnico usado na resposta.")
    definition: str = Field(..., description="Definição simples e literal do termo.")


class TutorAnswer(BaseModel):
    found_in_material: bool = Field(
        ..., description="true somente se o material responde à pergunta."
    )
    answer: str = Field(..., description="Resposta direta em 1 ou 2 frases curtas.")
    key_points: list[str] = Field(..., description="Até 3 tópicos curtos que completam a resposta.")
    example: str = Field(
        ..., description="Um exemplo concreto escrito no material, ou texto vazio se não houver."
    )
    terms: list[TutorTerm] = Field(..., description="Termos técnicos usados na resposta.")
    citations: list[int] = Field(..., description="Números dos trechos usados na resposta.")
