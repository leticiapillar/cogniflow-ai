import json
import re
from typing import Any

import pytest

from app.services.llm_provider import BaseLLMProvider
from app.services.mind_map.llm_schemas import ConceptSelection, MapOrganization, SectionExtraction
from app.services.mind_map.pipeline import MindMapPipeline
from app.services.mind_map.units import MapUnit
from app.services.prompts import map_section, reduce_map, rewrite_question, tutor_answer
from app.services.prompts.blocks import GROUNDING_RULES, MATERIAL_IS_DATA_RULE
from app.services.prompts.profiles import NEURODIVERGENT, PROFILES, AccessibilityProfile, get_profile
from app.services.tutor.llm_schemas import StandaloneQuestion, TutorAnswer
from tests.fakes.embeddings import FakeEmbeddingProvider

STUDENT_FACING = {
    "map_section": map_section.system_prompt(8),
    "organization": reduce_map.organization_system_prompt(3, 5, 5),
    "tutor_answer": tutor_answer.system_prompt(),
}
INTERNAL = {
    "selection": reduce_map.selection_system_prompt(),
    "rewrite_question": rewrite_question.system_prompt(),
}


@pytest.mark.parametrize("name", [*STUDENT_FACING, *INTERNAL])
def test_prompts_share_the_same_portuguese_structure(name: str) -> None:
    prompt = {**STUDENT_FACING, **INTERNAL}[name]
    assert "\nSua tarefa: " in prompt
    assert "\n\nCOMO RESPONDER:\n- " in prompt
    assert not re.search(r"\{[a-z_]+\}", prompt)  # no unfilled placeholders like {max_axes}


@pytest.mark.parametrize("name", list(STUDENT_FACING))
def test_student_facing_prompts_apply_grounding_and_the_profile(name: str) -> None:
    prompt = STUDENT_FACING[name]
    assert GROUNDING_RULES.splitlines()[1] in prompt
    assert NEURODIVERGENT.as_block() in prompt
    assert "alunos com TDAH e TEA" in prompt


def test_internal_prompts_do_not_carry_the_profile() -> None:
    for prompt in INTERNAL.values():
        assert "REGRAS DE ACESSIBILIDADE" not in prompt


def test_tutor_prompts_treat_the_material_as_data() -> None:
    assert MATERIAL_IS_DATA_RULE in tutor_answer.system_prompt()
    assert MATERIAL_IS_DATA_RULE in rewrite_question.system_prompt()


def test_no_rules_for_the_deaf_audience_in_this_version() -> None:
    every_prompt = " ".join([*STUDENT_FACING.values(), *INTERNAL.values()]).lower()
    for term in ("surd", "português como segunda língua", " l2", "libras", "sujeito → verbo"):
        assert term not in every_prompt
    assert set(PROFILES) == {"neurodivergent"}


@pytest.mark.parametrize(
    ("example", "model"),
    [
        (map_section.EXAMPLE_OUTPUT, SectionExtraction),
        (reduce_map.SELECTION_EXAMPLE, ConceptSelection),
        (reduce_map.ORGANIZATION_EXAMPLE, MapOrganization),
        (rewrite_question.EXAMPLE_OUTPUT, StandaloneQuestion),
        (tutor_answer.EXAMPLE_OUTPUT, TutorAnswer),
    ],
)
def test_few_shot_examples_follow_the_output_schema(example: str, model: type) -> None:
    model.model_validate_json(example)
    json.loads(example)


def test_map_example_cites_the_chunk_of_its_input() -> None:
    cited = {c for concept in json.loads(map_section.EXAMPLE_OUTPUT)["concepts"] for c in concept["source_chunks"]}
    assert cited == {int(i) for i in re.findall(r"\[Trecho (\d+)\]", map_section.EXAMPLE_INPUT)}


def test_unknown_profile_is_rejected() -> None:
    assert get_profile("neurodivergent") is NEURODIVERGENT
    with pytest.raises(ValueError, match="Unknown accessibility profile 'deaf'"):
        get_profile("deaf")


class RecordingLLM(BaseLLMProvider):
    model_name = "recording"

    def __init__(self) -> None:
        self.system_prompts: list[str] = []

    async def generate_json(self, system_prompt: str, user_prompt: str, json_schema: dict[str, Any]) -> str:
        self.system_prompts.append(system_prompt)
        return json.dumps({"concepts": []})


async def test_a_new_profile_reaches_the_model_without_changing_task_prompts() -> None:
    """Extension point: a future audience is a new AccessibilityProfile."""
    future = AccessibilityProfile(
        name="future", audience="um público futuro", rules=("Regra exclusiva do público futuro.",)
    )
    llm = RecordingLLM()
    pipeline = MindMapPipeline(llm=llm, embedder=FakeEmbeddingProvider(), profile=future)

    await pipeline.extract_unit(MapUnit(index=0, chunks=[(0, "Texto da aula.")]))

    [system] = llm.system_prompts
    assert "mapas mentais para um público futuro" in system
    assert "- Regra exclusiva do público futuro." in system
    assert "TDAH" not in system
    assert "Liste no máximo 8 conceitos" in system  # the task contract is unchanged
