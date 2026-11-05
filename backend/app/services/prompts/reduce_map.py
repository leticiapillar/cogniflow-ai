"""Task `reduce_map`: hierarchical concept selection and organization into study axes."""

from collections.abc import Sequence

from app.services.mind_map.llm_schemas import ConceptSelection, MapOrganization
from app.services.prompts.blocks import GROUNDING_RULES, compose_system_prompt, example_json
from app.services.prompts.profiles import DEFAULT_PROFILE, AccessibilityProfile

# (id, label, short summary) of each concept, as shown to the model.
ConceptLine = tuple[str, str, str]

RELATION_GUIDE = """TIPOS DE RELAÇÃO (do eixo para o conceito):
- has_part: o eixo inclui o conceito como uma de suas partes.
- is_a: o conceito é um tipo ou uma categoria do eixo.
- causes: o eixo produz ou causa o conceito.
- depends_on: o eixo depende do conceito para acontecer.
- precedes: o eixo vem antes do conceito em uma sequência.
- contrasts: o conceito é diferente ou oposto ao eixo.
- exemplified_by: o conceito é um exemplo do eixo.
Na dúvida, use has_part."""

SELECTION_EXAMPLE = example_json(ConceptSelection, {"concept_ids": ["c1", "c4"]})
ORGANIZATION_EXAMPLE = example_json(
    MapOrganization,
    {
        "topic": "Fotossíntese",
        "synthesis": "A fotossíntese é o processo em que as plantas produzem o próprio alimento. "
        "Ela usa luz, água e gás carbônico. Ela libera o oxigênio que os seres vivos respiram.",
        "axes": [
            {
                "title": "Etapas do processo",
                "summary": "As fases em que a fotossíntese acontece.",
                "concepts": [
                    {"id": "c2", "relation": "has_part"},
                    {"id": "c3", "relation": "has_part"},
                ],
            }
        ],
    },
)


def format_concept_list(concepts: Sequence[ConceptLine]) -> str:
    """One line per concept: '- <id> | <label> | <short summary>'."""
    return "\n".join(f"- {cid} | {label} | {summary}" for cid, label, summary in concepts)


def selection_system_prompt() -> str:
    # Internal step: its output is a list of ids, never shown to the student.
    return compose_system_prompt(
        "Você é um tutor que prepara mapas mentais de aulas.",
        "escolher, em uma lista de conceitos de uma aula, os mais importantes para entender o material.",
        GROUNDING_RULES,
        contract=[
            'Escolha apenas identificadores que estão na lista (por exemplo, "c3").',
            "Prefira conceitos centrais e definições. Deixe de fora detalhes e repetições.",
            f"Exemplo de saída: {SELECTION_EXAMPLE}",
        ],
    )


def selection_user_prompt(concepts: Sequence[ConceptLine], limit: int) -> str:
    return (
        f"Conceitos:\n{format_concept_list(concepts)}\n\n"
        f"Escolha no máximo {limit} conceitos e responda em JSON."
    )


def organization_system_prompt(
    min_axes: int,
    max_axes: int,
    max_concepts_per_axis: int,
    profile: AccessibilityProfile = DEFAULT_PROFILE,
) -> str:
    return compose_system_prompt(
        f"Você é um tutor que prepara mapas mentais para {profile.audience}.",
        "organizar os conceitos de uma aula em eixos de estudo, do geral para o específico.",
        GROUNDING_RULES,
        profile.as_block(),
        RELATION_GUIDE,
        contract=[
            '"topic": tema central da aula, com 1 a 6 palavras.',
            '"synthesis": de 2 a 3 frases curtas: o que é o tema e por que ele é importante.',
            f'"axes": de {min_axes} a {max_axes} eixos de estudo, na ORDEM em que o aluno deve estudar '
            "(do básico para o avançado, seguindo a ordem do material).",
            f'Cada eixo: "title" com 1 a 6 palavras, "summary" com uma frase curta e "concepts" '
            f"com 1 a {max_concepts_per_axis} conceitos.",
            "Use apenas identificadores de conceitos que estão na lista. Cada conceito aparece em no máximo um eixo.",
            "Um eixo agrupa conceitos relacionados. O título do eixo não pode ser igual ao nome de um dos seus conceitos.",
            f"Exemplo de formato: {ORGANIZATION_EXAMPLE}",
        ],
    )


def organization_user_prompt(concepts: Sequence[ConceptLine]) -> str:
    return (
        "Conceitos da aula, na ordem em que aparecem no material:\n"
        f"{format_concept_list(concepts)}\n\n"
        "Organize os conceitos em eixos de estudo e responda em JSON."
    )
