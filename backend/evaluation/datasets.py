"""Evaluation data: reference entities for the mind map and questions for the tutor.

The tutor set uses `fotossintese-texto-selecionavel.pdf` (3 pages). Expected pages and
keywords were taken from the PDF text; `answer_keywords` are alternatives (any one is
enough) checked in the answer, `pages` are the pages where the information is written.
"""

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PHOTOSYNTHESIS_PDF = PROJECT_ROOT / "fotossintese-texto-selecionavel.pdf"


@dataclass(frozen=True)
class MapReference:
    name: str
    pdf_bytes: bytes
    expected_entities: tuple[str, ...]


@dataclass(frozen=True)
class TutorQuestion:
    question: str
    in_material: bool
    pages: tuple[int, ...] = ()
    answer_keywords: tuple[str, ...] = field(default_factory=tuple)


PHOTOSYNTHESIS_ENTITIES = (
    "Fotossíntese",
    "Clorofila",
    "Cloroplastos",
    "Glicose",
    "Gás carbônico",
    "Oxigênio",
    "Pigmento",
    "Plantas carnívoras",
)

TUTOR_QUESTIONS: tuple[TutorQuestion, ...] = (
    TutorQuestion("O que é a fotossíntese?", True, (1,), ("luz", "glicose", "carboidrato", "alimento", "autotrófico")),
    TutorQuestion("Quais seres realizam a fotossíntese?", True, (1,), ("plantas", "algas", "cianobactérias", "clorofilados")),
    TutorQuestion("Quais substâncias a planta usa para fazer a fotossíntese?", True, (1,), ("gás carbônico", "co2", "co₂", "água")),
    TutorQuestion("Qual gás é liberado na fotossíntese?", True, (1,), ("oxigênio", "o2", "o₂")),
    TutorQuestion("O que são os cloroplastos?", True, (1,), ("organela",)),
    TutorQuestion("Por que os cloroplastos são verdes?", True, (1,), ("clorofila",)),
    TutorQuestion("Quais cores de luz a clorofila absorve?", True, (2,), ("azul", "violeta", "vermelho")),
    TutorQuestion("Para que serve a glicose produzida pela planta?", True, (2,), ("amido", "sacarose", "respiração", "celulose", "energia")),
    TutorQuestion("Por que a fotossíntese é importante para a vida no planeta?", True, (2,), ("cadeia alimentar", "oxigênio")),
    TutorQuestion("As plantas carnívoras também fazem fotossíntese?", True, (2,), ("sim", "precisam", "necessitam", "realizam", "fazem")),
    # Same subject, not written in the material: only the LLM can refuse it.
    TutorQuestion("Quem descobriu a fotossíntese?", False),
    TutorQuestion("O que é o ciclo de Krebs?", False),
    TutorQuestion("Como os peixes respiram embaixo da água?", False),
    TutorQuestion("Qual é a capital da França?", False),
    TutorQuestion("Quanto custa um quilo de arroz no mercado?", False),
)


def map_references(academic_samples: int) -> list[MapReference]:
    """The photosynthesis PDF plus the first `academic_samples` synthetic handouts."""
    from tests.fixtures.academic_materials import TWENTY_ACADEMIC_MATERIALS, build_valid_pdf_bytes

    references = [MapReference("fotossintese-texto-selecionavel.pdf", PHOTOSYNTHESIS_PDF.read_bytes(), PHOTOSYNTHESIS_ENTITIES)]
    for sample in TWENTY_ACADEMIC_MATERIALS[:academic_samples]:
        references.append(MapReference(sample.filename, build_valid_pdf_bytes(sample.content), sample.expected_entities))
    return references
