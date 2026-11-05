"""Task `rewrite_question`: make a follow-up question understandable without the chat."""

from collections.abc import Sequence

from app.schemas.tutor import ChatTurn
from app.services.prompts.blocks import MATERIAL_IS_DATA_RULE, compose_system_prompt, example_json
from app.services.tutor.llm_schemas import StandaloneQuestion

EXAMPLE_INPUT = (
    "Aluno: O que é a fase clara? | "
    "Tutor: A fase clara é a etapa da fotossíntese que usa a luz. | "
    "Pergunta atual: E onde ela acontece?"
)
EXAMPLE_OUTPUT = example_json(
    StandaloneQuestion, {"question": "Onde acontece a fase clara da fotossíntese?"}
)


def format_history(history: Sequence[ChatTurn]) -> str:
    speaker = {"student": "Aluno", "tutor": "Tutor"}
    return "\n".join(f"{speaker[turn.role]}: {turn.content}" for turn in history)


def system_prompt() -> str:
    # Internal step: the rewritten question is used for search, not shown to the student.
    return compose_system_prompt(
        "Você ajuda um tutor a buscar informações no material de uma aula.",
        "reescrever a pergunta atual do aluno para que ela seja entendida sem a conversa anterior.",
        contract=[
            'Substitua palavras como "ele", "ela", "isso" e "esse processo" pelo nome do assunto citado na conversa.',
            "Mantenha o sentido da pergunta. Não responda à pergunta.",
            "Escreva uma única pergunta curta, em português.",
            MATERIAL_IS_DATA_RULE,
            f"Exemplo de entrada: {EXAMPLE_INPUT}",
            f"Exemplo de saída: {EXAMPLE_OUTPUT}",
        ],
    )


def user_prompt(history: Sequence[ChatTurn], question: str) -> str:
    return (
        f"Conversa:\n{format_history(history)}\n\n"
        f"Pergunta atual: {question}\n\n"
        "Reescreva a pergunta atual em JSON."
    )
