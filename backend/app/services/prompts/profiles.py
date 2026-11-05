"""Accessibility profiles: how student-facing text must be written for each audience.

This version serves neurodivergent students (ADHD and autism). Other audiences (for
example deaf students reading Portuguese as a second language) are added as new
profiles, without rewriting the task prompts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AccessibilityProfile:
    name: str
    audience: str
    rules: tuple[str, ...]

    def as_block(self) -> str:
        lines = "\n".join(f"- {rule}" for rule in self.rules)
        return f"REGRAS DE ACESSIBILIDADE ({self.audience}):\n{lines}"


NEURODIVERGENT = AccessibilityProfile(
    name="neurodivergent",
    audience="alunos com TDAH e TEA",
    rules=(
        # TEA: literal language and predictability.
        "Linguagem literal e concreta. Sem metáforas, ironia, expressões figuradas ou perguntas retóricas.",
        "Use sempre a mesma estrutura de resposta.",
        # TDAH: low working-memory load.
        "Frases curtas, com no máximo 20 palavras, em ordem direta: sujeito, verbo, complemento.",
        "Uma ideia por frase.",
        "Coloque a informação principal primeiro.",
        "Escreva siglas por extenso na primeira menção, quando o material trouxer o significado.",
        # Both.
        "Explique cada termo técnico com palavras simples.",
    ),
)

PROFILES: dict[str, AccessibilityProfile] = {NEURODIVERGENT.name: NEURODIVERGENT}
DEFAULT_PROFILE = NEURODIVERGENT


def get_profile(name: str) -> AccessibilityProfile:
    try:
        return PROFILES[name]
    except KeyError:
        supported = ", ".join(sorted(PROFILES))
        raise ValueError(f"Unknown accessibility profile '{name}'. Supported: {supported}.") from None
