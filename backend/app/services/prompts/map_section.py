"""Task `map_section` (Map step): key concepts of one section of the material."""

from app.services.mind_map.llm_schemas import SectionExtraction
from app.services.mind_map.units import MapUnit
from app.services.prompts.blocks import GROUNDING_RULES, compose_system_prompt, example_json
from app.services.prompts.profiles import DEFAULT_PROFILE, AccessibilityProfile

EXAMPLE_INPUT = (
    "[Trecho 4] Cloroplastos são organelas presentes nas células das plantas. "
    "Eles contêm clorofila, um pigmento verde que absorve a luz."
)
EXAMPLE_OUTPUT = example_json(
    SectionExtraction,
    {
        "concepts": [
            {
                "label": "Cloroplasto",
                "summary": "O cloroplasto é uma organela das células das plantas. Ele contém clorofila.",
                "source_chunks": [4],
            },
            {
                "label": "Clorofila",
                "summary": "A clorofila é um pigmento verde. Ela absorve a luz.",
                "source_chunks": [4],
            },
        ]
    },
)


def system_prompt(max_concepts: int, profile: AccessibilityProfile = DEFAULT_PROFILE) -> str:
    return compose_system_prompt(
        f"Você é um tutor que prepara mapas mentais para {profile.audience}.",
        "ler UMA seção de uma aula e listar os conceitos-chave dessa seção.",
        GROUNDING_RULES,
        profile.as_block(),
        contract=[
            f"Liste no máximo {max_concepts} conceitos, os mais importantes para entender a seção.",
            '"label": nome do conceito com 1 a 6 palavras. Use um substantivo. '
            'Não termine com "de", "da", "do", "para", "ou", "e".',
            '"summary": definição literal do conceito em 1 ou 2 frases curtas.',
            '"examples": de 0 a 2 exemplos concretos que estejam escritos no texto. Se não houver, use [].',
            '"acronyms": siglas do conceito com o significado escrito no texto. Se não houver, use [].',
            '"source_chunks": os números dos trechos (por exemplo, 3 em "[Trecho 3]") onde o conceito aparece.',
            "Se a seção não tiver conteúdo de estudo (só bibliografia, sumário ou créditos), "
            'responda {"concepts": []}.',
            f"Exemplo de entrada: {EXAMPLE_INPUT}",
            f"Exemplo de saída: {EXAMPLE_OUTPUT}",
        ],
    )


def user_prompt(unit: MapUnit) -> str:
    chunks = "\n".join(f"[Trecho {index}] {text}" for index, text in unit.chunks)
    return f"Seção: {unit.title or 'Sem título'}\n\n{chunks}\n\nListe os conceitos-chave desta seção em JSON."
