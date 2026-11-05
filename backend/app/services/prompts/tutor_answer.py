"""Task `tutor_answer`: answer the student's question using only the class material."""

from collections.abc import Sequence

from app.repositories.models import DocumentChunkModel
from app.schemas.tutor import ChatTurn
from app.services.prompts.blocks import (
    GROUNDING_RULES,
    MATERIAL_IS_DATA_RULE,
    compose_system_prompt,
    example_json,
)
from app.services.prompts.profiles import DEFAULT_PROFILE, AccessibilityProfile
from app.services.prompts.rewrite_question import format_history
from app.services.text_processing import prepare_chunk_text
from app.services.tutor.llm_schemas import TutorAnswer

EXAMPLE_INPUT = "Pergunta: O que a clorofila faz?"
EXAMPLE_OUTPUT = example_json(
    TutorAnswer,
    {
        "found_in_material": True,
        "answer": "A clorofila absorve a luz do sol. A planta usa essa energia na fotossíntese.",
        "key_points": ["A clorofila é um pigmento verde.", "Ela fica dentro dos cloroplastos."],
        "example": "",
        "terms": [{"term": "Pigmento", "definition": "Substância que dá cor."}],
        "citations": [4],
    },
)


def system_prompt(profile: AccessibilityProfile = DEFAULT_PROFILE) -> str:
    return compose_system_prompt(
        f"Você é um tutor de aula para {profile.audience}.",
        "responder à dúvida do aluno usando SOMENTE o material da aula.",
        GROUNDING_RULES
        + f"\n- {MATERIAL_IS_DATA_RULE}"
        + '\n- Se o material não responde à pergunta, use "found_in_material": false e deixe os outros campos vazios.',
        profile.as_block(),
        contract=[
            "Responda sempre nesta mesma estrutura.",
            '"answer": a resposta direta, em 1 ou 2 frases curtas.',
            '"key_points": até 3 tópicos curtos que completam a resposta. Um fato por tópico.',
            '"example": um exemplo concreto que esteja escrito no material. Se não houver, use "".',
            '"terms": os termos técnicos usados na resposta, cada um com uma definição simples.',
            '"citations": os números dos trechos (por exemplo, 3 em "[Trecho 3]") que sustentam a resposta.',
            f"Exemplo de entrada: {EXAMPLE_INPUT}",
            f"Exemplo de saída: {EXAMPLE_OUTPUT}",
        ],
    )


def format_material(chunks: Sequence[DocumentChunkModel]) -> str:
    lines = []
    for chunk in chunks:
        pages = (
            f"página {chunk.page_start}"
            if chunk.page_start == chunk.page_end
            else f"páginas {chunk.page_start}-{chunk.page_end}"
        )
        text = prepare_chunk_text(chunk.content) or chunk.content
        lines.append(f"[Trecho {chunk.chunk_index}] ({pages}) {text}")
    return "<MATERIAL>\n" + "\n".join(lines) + "\n</MATERIAL>"


def user_prompt(
    question: str,
    chunks: Sequence[DocumentChunkModel],
    history: Sequence[ChatTurn] = (),
    concept_label: str | None = None,
) -> str:
    parts = [format_material(chunks)]
    if history:
        parts.append(f"Conversa anterior:\n{format_history(history)}")
    if concept_label:
        parts.append(f"O aluno está estudando o conceito: {concept_label}")
    parts.append(f"Pergunta: {question}\n\nResponda em JSON.")
    return "\n\n".join(parts)
