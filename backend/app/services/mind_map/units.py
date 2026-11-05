from dataclasses import dataclass, field
from typing import Protocol, Sequence

from app.services.text_processing import prepare_chunk_text

# A unit must fit, with prompt and answer, in the 8192-token context of a 3B model.
UNIT_MAX_CHARS = 6000
# Adjacent small sections are merged up to this size to save LLM calls
# without overloading a small model with too much text at once.
UNIT_MERGE_TARGET_CHARS = 3000


class ChunkLike(Protocol):
    chunk_index: int
    content: str
    section_title: str | None


@dataclass
class MapUnit:
    """Text sent to one Map call: one section, several small ones, or part of a large one."""

    index: int
    titles: list[str] = field(default_factory=list)
    chunks: list[tuple[int, str]] = field(default_factory=list)

    @property
    def title(self) -> str | None:
        return " / ".join(self.titles)[:255] if self.titles else None

    @property
    def chunk_indices(self) -> list[int]:
        return [index for index, _ in self.chunks]

    @property
    def size(self) -> int:
        return sum(len(text) for _, text in self.chunks)


def _group_by_section(chunks: Sequence[ChunkLike]) -> list[tuple[str | None, list[tuple[int, str]]]]:
    """Group consecutive chunks of the same section, keeping only readable text."""
    sections: list[tuple[str | None, list[tuple[int, str]]]] = []
    for chunk in sorted(chunks, key=lambda c: c.chunk_index):
        text = prepare_chunk_text(chunk.content)
        if sections and sections[-1][0] == chunk.section_title:
            if text:
                sections[-1][1].append((chunk.chunk_index, text))
            continue
        sections.append((chunk.section_title, [(chunk.chunk_index, text)] if text else []))
    return [(title, items) for title, items in sections if items]


def _split_large_section(items: list[tuple[int, str]], max_chars: int) -> list[list[tuple[int, str]]]:
    pieces: list[list[tuple[int, str]]] = [[]]
    size = 0
    for item in items:
        if pieces[-1] and size + len(item[1]) > max_chars:
            pieces.append([])
            size = 0
        pieces[-1].append(item)
        size += len(item[1])
    return pieces


def build_map_units(
    chunks: Sequence[ChunkLike],
    max_chars: int = UNIT_MAX_CHARS,
    merge_target_chars: int = UNIT_MERGE_TARGET_CHARS,
) -> list[MapUnit]:
    """Turn ordered chunks into Map units following the document's own sections."""
    units: list[MapUnit] = []
    mergeable = False  # whether the last unit holds whole small sections only

    for title, items in _group_by_section(chunks):
        section_size = sum(len(text) for _, text in items)
        if section_size > max_chars:
            for piece in _split_large_section(items, max_chars):
                units.append(
                    MapUnit(index=len(units), titles=[title] if title else [], chunks=piece)
                )
            mergeable = False
            continue

        if mergeable and units and units[-1].size + section_size <= merge_target_chars:
            units[-1].chunks.extend(items)
            if title:
                units[-1].titles.append(title)
            continue

        units.append(MapUnit(index=len(units), titles=[title] if title else [], chunks=items))
        mergeable = section_size <= merge_target_chars
    return units
