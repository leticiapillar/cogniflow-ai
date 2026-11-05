"""Shapes the LLM must answer with. Their JSON Schema is sent as Ollama's `format`."""

from pydantic import BaseModel, Field

from app.schemas.mind_map import RelationType


class ExtractedAcronym(BaseModel):
    acronym: str = Field(..., description="Sigla exatamente como aparece no texto.")
    expansion: str = Field(..., description="Significado completo da sigla, segundo o texto.")


class ExtractedExample(BaseModel):
    label: str = Field(..., description="Nome curto do exemplo, de 1 a 6 palavras.")
    summary: str = Field(..., description="Uma frase curta e literal descrevendo o exemplo.")


class ExtractedConcept(BaseModel):
    label: str = Field(..., description="Nome do conceito, de 1 a 6 palavras.")
    summary: str = Field(..., description="Definição literal em 1 ou 2 frases curtas.")
    acronyms: list[ExtractedAcronym] = Field(default_factory=list)
    examples: list[ExtractedExample] = Field(
        default_factory=list, description="De 0 a 2 exemplos concretos citados no texto."
    )
    source_chunks: list[int] = Field(
        ..., description="Números dos trechos onde o conceito aparece."
    )


class SectionExtraction(BaseModel):
    """Map step: key concepts of one section."""

    concepts: list[ExtractedConcept] = Field(
        ..., description="Conceitos-chave da seção. Lista vazia se não houver conteúdo de estudo."
    )


class ConceptSelection(BaseModel):
    """Hierarchical reduce step: the most important concepts of a group."""

    concept_ids: list[str] = Field(..., description="Identificadores dos conceitos escolhidos.")


class AxisConcept(BaseModel):
    id: str = Field(..., description="Identificador do conceito, por exemplo c3.")
    relation: RelationType = Field(..., description="Tipo de relação entre o eixo e o conceito.")


class StudyAxis(BaseModel):
    title: str = Field(..., description="Nome do eixo de estudo, de 1 a 6 palavras.")
    summary: str = Field(..., description="Uma frase curta explicando o eixo.")
    concepts: list[AxisConcept] = Field(..., description="De 1 a 5 conceitos do eixo.")


class MapOrganization(BaseModel):
    """Final reduce step: study axes in reading order and the root synthesis."""

    topic: str = Field(..., description="Tema central da aula, de 1 a 6 palavras.")
    synthesis: str = Field(
        ..., description="De 2 a 3 frases curtas: o que é o tema e por que ele importa."
    )
    axes: list[StudyAxis] = Field(..., description="Eixos de estudo na ordem de leitura sugerida.")
