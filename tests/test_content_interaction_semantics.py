from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from agents.implementation.content_interaction_agent import run_content_interaction_agent
from schemas.implementation.common import QuizItem
from schemas.implementation.content_interaction import (
    ContentInteractionInput,
    ContentInteractionOutput,
)
from schemas.implementation.implementation_spec import parse_markdown_spec
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from tests.fakes import FakeLLMClient

REPO_ROOT = Path(__file__).resolve().parents[1]


class ScriptedContentClient:
    def __init__(
        self,
        *,
        initial_content_output: ContentInteractionOutput,
        regenerated_items: list[QuizItem] | None = None,
    ) -> None:
        self.initial_content_output = initial_content_output
        self.regenerated_items = list(regenerated_items or [])
        self.calls: list[str] = []

    def generate_json(self, *, prompt: str, response_model, system_prompt: str | None = None):
        self.calls.append(response_model.__name__)
        if response_model is ContentInteractionOutput:
            return response_model.model_validate(
                self.initial_content_output.model_dump(mode="json")
            )
        if response_model is QuizItem:
            if not self.regenerated_items:
                raise AssertionError("Unexpected regeneration request.")
            return response_model.model_validate(
                self.regenerated_items.pop(0).model_dump(mode="json")
            )
        raise AssertionError(f"Unexpected response model: {response_model.__name__}")


def _build_input_models() -> tuple[SpecIntakeOutput, RequirementMappingOutput]:
    fake = FakeLLMClient()
    return (
        fake.generate_json(prompt="", response_model=SpecIntakeOutput),
        fake.generate_json(prompt="", response_model=RequirementMappingOutput),
    )


def _build_input(content_output: ContentInteractionOutput, client) -> ContentInteractionOutput:
    spec_intake_output, requirement_mapping_output = _build_input_models()
    implementation_spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    return run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )


def test_label_correction_only_does_not_trigger_regeneration() -> None:
    fake = FakeLLMClient()
    content_output = fake.generate_json(prompt="", response_model=ContentInteractionOutput)
    content_output.items[0].quiz_type = "더 좋은 질문 고르기"
    content_output.items[0].learning_dimension = "종합성"

    client = ScriptedContentClient(initial_content_output=content_output)
    result = _build_input(content_output, client)

    assert result.items[0].quiz_type == "질문에서 빠진 요소 찾기"
    assert result.items[0].learning_dimension == "맥락성"
    assert result.semantic_validation is not None
    assert result.semantic_validation.regeneration_count == 0
    assert client.calls == ["ContentInteractionOutput"]


def test_semantic_mismatch_triggers_single_item_regeneration() -> None:
    fake = FakeLLMClient()
    content_output = fake.generate_json(prompt="", response_model=ContentInteractionOutput)
    broken_item = deepcopy(content_output.items[2])
    broken_item.question = "다음 중 더 좋은 질문은 무엇일까?"
    broken_item.choices = ["맥락 정보", "색깔", "느낌"]
    broken_item.correct_choice = "맥락 정보"
    broken_item.explanation = "정답 선택지는 빠진 정보가 무엇인지 보여 줍니다."
    broken_item.learning_point = "질문에서 빠진 맥락 정보를 채우면 더 좋은 질문이 됩니다."
    content_output.items[2] = broken_item

    regenerated_item = QuizItem.model_validate(
        {
            "item_id": broken_item.item_id,
            "quiz_type": "더 좋은 질문 고르기",
            "learning_dimension": "맥락성",
            "title": "재생성된 더 좋은 질문 고르기",
            "question": "다음 중 더 좋은 질문은 무엇일까?",
            "choices": [
                "비유가 뭐야?",
                "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 모르겠어.",
                "문학은 어려워.",
            ],
            "correct_choice": "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 모르겠어.",
            "explanation": "과목과 예시 문장이 드러나 질문의 맥락을 더 잘 이해할 수 있습니다.",
            "learning_point": "좋은 질문은 상황과 배경 같은 맥락 정보를 함께 드러냅니다.",
        }
    )

    client = ScriptedContentClient(
        initial_content_output=content_output,
        regenerated_items=[regenerated_item],
    )
    result = _build_input(content_output, client)

    assert result.semantic_validation is not None
    assert result.semantic_validation.regeneration_count == 1
    assert broken_item.item_id in result.semantic_validation.regenerated_item_ids
    assert client.calls == ["ContentInteractionOutput", "QuizItem"]


def test_regeneration_failure_raises_value_error() -> None:
    fake = FakeLLMClient()
    content_output = fake.generate_json(prompt="", response_model=ContentInteractionOutput)
    broken_item = deepcopy(content_output.items[2])
    broken_item.question = "다음 중 더 좋은 질문은 무엇일까?"
    broken_item.choices = ["맥락 정보", "색깔", "느낌"]
    broken_item.correct_choice = "맥락 정보"
    broken_item.explanation = "정답 선택지는 빠진 정보가 무엇인지 보여 줍니다."
    broken_item.learning_point = "질문에서 빠진 맥락 정보를 채우면 더 좋은 질문이 됩니다."
    content_output.items[2] = broken_item

    invalid_regenerated_item = QuizItem.model_validate(
        {
            "item_id": broken_item.item_id,
            "quiz_type": "더 좋은 질문 고르기",
            "learning_dimension": "구체성",
            "title": "여전히 잘못된 문항",
            "question": "다음 중 더 좋은 질문은 무엇일까?",
            "choices": ["맥락 정보", "색깔", "느낌"],
            "correct_choice": "맥락 정보",
            "explanation": "정답 선택지는 빠진 정보가 무엇인지 보여 줍니다.",
            "learning_point": "질문에서 빠진 맥락 정보를 채우면 더 좋은 질문이 됩니다.",
        }
    )

    client = ScriptedContentClient(
        initial_content_output=content_output,
        regenerated_items=[invalid_regenerated_item],
    )

    with pytest.raises(ValueError):
        _build_input(content_output, client)
