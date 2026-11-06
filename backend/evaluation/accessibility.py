"""Heuristic checks of the neurodivergent profile (TDAH/TEA) on generated text.

They are proxies, not a clinical assessment: short sentences, short labels, no
rhetorical questions and none of a list of common figurative expressions.
"""

from collections.abc import Iterable
from dataclasses import dataclass
import re

MAX_SENTENCE_WORDS = 20
MAX_LABEL_WORDS = 6

# Frequent figurative phrasings in Portuguese teaching material (TEA: literal language).
FIGURATIVE_PATTERNS = (
    r"\bcomo se\b",
    r"\bcoração d[oae]\b",
    r"\bporta de entrada\b",
    r"\bchave para\b",
    r"\bmotor d[oae]\b",
    r"\bfábrica d[oae]\b",
    r"\bcomo uma fábrica\b",
    r"\bpulm(ão|ões) d[oae]\b",
    r"\bverdadeir[oa] heró",
    r"\bmágica\b",
)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT.split(text.strip()) if part.strip()]


@dataclass(frozen=True)
class AccessibilityReport:
    texts: int
    sentences: int
    short_sentence_rate: float
    label_rate: float | None
    rhetorical_questions: int
    figurative_expressions: int
    adherence: float  # share of texts passing every check

    def as_dict(self) -> dict[str, float | int | None]:
        return self.__dict__.copy()


def _figurative(text: str) -> int:
    return sum(1 for pattern in FIGURATIVE_PATTERNS if re.search(pattern, text, re.IGNORECASE))


def evaluate_texts(texts: Iterable[str], labels: Iterable[str] = ()) -> AccessibilityReport:
    texts = [text for text in texts if text and text.strip()]
    labels = [label for label in labels if label and label.strip()]
    all_sentences = [sentence for text in texts for sentence in sentences(text)]
    short = [s for s in all_sentences if len(s.split()) <= MAX_SENTENCE_WORDS]
    rhetorical = sum(text.count("?") for text in texts)
    figurative = sum(_figurative(text) for text in texts)

    def passes(text: str) -> bool:
        return (
            all(len(s.split()) <= MAX_SENTENCE_WORDS for s in sentences(text))
            and "?" not in text
            and _figurative(text) == 0
        )

    return AccessibilityReport(
        texts=len(texts),
        sentences=len(all_sentences),
        short_sentence_rate=len(short) / len(all_sentences) if all_sentences else 1.0,
        label_rate=(
            sum(1 for label in labels if len(label.split()) <= MAX_LABEL_WORDS) / len(labels) if labels else None
        ),
        rhetorical_questions=rhetorical,
        figurative_expressions=figurative,
        adherence=sum(1 for text in texts if passes(text)) / len(texts) if texts else 1.0,
    )
