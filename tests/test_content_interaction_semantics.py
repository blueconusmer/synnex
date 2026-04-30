from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from agents.implementation.content_interaction_agent import run_content_interaction_agent
from schemas.implementation.common import InteractionUnit, QuizItem
from schemas.implementation.content_interaction import (
    ContentInteractionInput,
    ContentInteractionOutput,
)
from schemas.implementation.implementation_spec import ImplementationSpec, parse_markdown_spec
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


def _build_input(
    content_output: ContentInteractionOutput,
    client,
    implementation_spec: ImplementationSpec | None = None,
) -> ContentInteractionOutput:
    spec_intake_output, requirement_mapping_output = _build_input_models()
    implementation_spec = implementation_spec or parse_markdown_spec(
        REPO_ROOT / "inputs" / "quiz_service_spec.md"
    )
    return run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )


def test_interaction_unit_metadata_uses_independent_default_dict() -> None:
    first = InteractionUnit(unit_id="u1", interaction_type="feedback")
    second = InteractionUnit(unit_id="u2", interaction_type="feedback")

    first.metadata["key"] = "value"

    assert second.metadata == {}


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
    assert result.interaction_mode == "quiz"
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True
    assert any(unit.interaction_type == "feedback" for unit in result.interaction_units)
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
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True
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


def test_coaching_mode_uses_interaction_units_as_primary_contract() -> None:
    spec_intake_output = SpecIntakeOutput.model_validate(
        {
            "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
            "service_summary": "질문 입력을 받아 되묻기와 진단으로 개선 방향을 제안하는 코칭형 서비스다.",
            "normalized_requirements": ["사용자 질문 입력", "진단", "코칭 피드백"],
            "delivery_expectations": ["interaction_units 생성"],
            "acceptance_focus": ["interaction_units 구조 validator 통과"],
        }
    )
    requirement_mapping_output = RequirementMappingOutput.model_validate(
        {
            "implementation_targets": ["coaching interaction flow"],
            "file_plan": [],
            "quiz_generation_requirements": {
                "quiz_type_count": 0,
                "items_per_type": 0,
                "total_items": 0,
                "required_fields": [],
            },
            "app_constraints": ["chat-like follow-up flow"],
            "test_strategy": ["interaction validator"],
        }
    )
    implementation_spec = ImplementationSpec(
        source_path=str(REPO_ROOT / "inputs" / "260428_챗봇"),
        service_name="질문 개선 코칭 챗봇",
        target_framework="streamlit",
        team_identity="교육 서비스 구현 전문 AI Agent 팀",
        service_purpose="질문 입력을 받아 진단과 되묻기로 개선 방향을 제안하는 챗봇 코칭 서비스",
        target_users=["중학생"],
        learning_goals=["구체성", "맥락성", "목적성"],
        core_features=["follow_up", "diagnosis", "coaching_feedback"],
        total_count=0,
        items_per_type=0,
        content_interaction_direction=["/api/chat", "질문 입력", "되묻기", "진단"],
        excluded_scope=[],
        expected_outputs=["chat demo"],
        acceptance_criteria=["interaction_units가 유효해야 한다."],
        constraints=[],
    )
    content_output = ContentInteractionOutput.model_validate(
        {
            "service_summary": "질문 개선 코칭 챗봇용 상호작용 구조다.",
            "interaction_units": [
                {
                    "unit_id": "chat_input",
                    "interaction_type": "free_text_input",
                    "title": "질문 입력",
                    "learner_action": "현재 질문을 입력한다.",
                    "system_response": "질문을 받으면 진단을 시작한다.",
                    "input_format": "free_text",
                    "next_step": "chat_diagnosis",
                    "metadata": {"purpose": "user_input"},
                },
                {
                    "unit_id": "chat_diagnosis",
                    "interaction_type": "diagnosis",
                    "title": "질문 진단",
                    "system_response": "질문의 구체성, 맥락성, 목적성을 진단한다.",
                    "next_step": "chat_feedback",
                    "metadata": {"diagnosis_criteria": ["구체성", "맥락성", "목적성"]},
                },
                {
                    "unit_id": "chat_feedback",
                    "interaction_type": "coaching_feedback",
                    "title": "개선 피드백",
                    "system_response": "더 구체적인 질문으로 바꾸는 방향을 제안한다.",
                    "next_step": "next_step_guide",
                    "metadata": {"feedback_scope": "question_improvement"},
                },
                {
                    "unit_id": "next_step_guide",
                    "interaction_type": "next_step_guide",
                    "title": "다음 단계",
                    "system_response": "다시 질문을 입력하거나 종료할 수 있다.",
                    "next_step": "END",
                    "metadata": {"completion": "guided"},
                },
            ],
            "flow_notes": ["자유 입력 -> 진단 -> 코칭 피드백 -> 다음 단계 안내"],
            "evaluation_rules": {
                "diagnosis_criteria": ["구체성", "맥락성", "목적성"],
                "feedback_policy": "사용자 자유 입력을 기준으로 개선 방향을 제안한다.",
            },
        }
    )

    client = ScriptedContentClient(initial_content_output=content_output)
    result = run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )

    assert result.interaction_mode == "coaching"
    assert "coaching markers detected" in result.interaction_mode_reason
    assert result.semantic_validation is None
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True
    assert result.items == []
    assert any(unit.interaction_type == "coaching_feedback" for unit in result.interaction_units)
    assert "diagnosis_criteria" in result.evaluation_rules


def test_question_word_does_not_trigger_quest_quiz_marker_for_chatbot_service() -> None:
    spec_intake_output = SpecIntakeOutput.model_validate(
        {
            "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
            "service_summary": "Question Coaching Chatbot은 질문 입력과 되묻기로 개선 방향을 제안한다.",
            "normalized_requirements": ["/api/chat", "질문 입력", "되묻기", "coaching"],
            "delivery_expectations": ["interaction_units 생성"],
            "acceptance_focus": ["interaction_mode가 quiz로 오판되지 않아야 한다."],
        }
    )
    requirement_mapping_output = RequirementMappingOutput.model_validate(
        {
            "implementation_targets": ["chatbot interaction flow"],
            "file_plan": [],
            "quiz_generation_requirements": {
                "quiz_type_count": 0,
                "items_per_type": 0,
                "total_items": 0,
                "required_fields": [],
            },
            "app_constraints": ["질문 입력 -> 진단 -> 되묻기 -> 결과"],
            "test_strategy": ["interaction validator"],
        }
    )
    implementation_spec = ImplementationSpec(
        source_path=str(REPO_ROOT / "inputs" / "260428_챗봇"),
        service_name="Question Coaching Chatbot",
        target_framework="streamlit",
        team_identity="교육 서비스 구현 전문 AI Agent 팀",
        service_purpose="질문 입력을 받아 진단과 되묻기로 개선 방향을 제안하는 챗봇 코칭 서비스",
        target_users=["중학생"],
        learning_goals=["구체성", "맥락성", "목적성"],
        core_features=["need_specificity", "need_context", "need_purpose", "completed"],
        total_count=4,
        items_per_type=0,
        content_interaction_direction=["/api/chat", "awaiting_input", "diagnosing", "completed"],
        excluded_scope=[],
        expected_outputs=["질문 입력 화면", "되묻기 화면", "재요청 결과 화면"],
        acceptance_criteria=["interaction_units가 유효해야 한다."],
        constraints=[],
        content_distribution={
            "need_specificity": 1,
            "need_context": 1,
            "need_purpose": 1,
            "completed": 1,
        },
    )
    content_output = ContentInteractionOutput.model_validate(
        {
            "service_summary": "Question Coaching Chatbot interaction flow.",
            "interaction_units": [
                {
                    "unit_id": "chat_input",
                    "interaction_type": "free_text_input",
                    "title": "질문 입력",
                    "learner_action": "질문을 입력한다.",
                    "system_response": "입력된 질문을 진단한다.",
                    "input_format": "free_text",
                    "next_step": "chat_feedback",
                    "metadata": {"purpose": "user_input"},
                },
                {
                    "unit_id": "chat_feedback",
                    "interaction_type": "coaching_feedback",
                    "title": "개선 피드백",
                    "system_response": "부족한 요소 하나만 짚어 준다.",
                    "next_step": "END",
                    "metadata": {"diagnosis_criteria": ["구체성", "맥락성", "목적성"]},
                },
            ],
            "flow_notes": ["질문 입력 -> 코칭 피드백"],
        }
    )

    client = ScriptedContentClient(initial_content_output=content_output)
    result = run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )

    assert result.interaction_mode == "coaching"
    assert "coaching markers detected" in result.interaction_mode_reason
    assert "quest" not in result.interaction_mode_reason
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True
    assert result.semantic_validation is None


def test_non_quiz_content_types_prefer_coaching_over_incidental_quiz_words() -> None:
    spec_intake_output = SpecIntakeOutput.model_validate(
        {
            "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
            "service_summary": "질문 코칭 챗봇은 정답을 바로 주지 않고 되묻기로 질문 개선을 돕는다.",
            "normalized_requirements": ["정답 직접 제공 금지", "질문 입력", "되묻기", "/api/chat"],
            "delivery_expectations": ["interaction_units 생성"],
            "acceptance_focus": ["quiz-like content type marker가 없으면 coaching으로 해석되어야 한다."],
        }
    )
    requirement_mapping_output = RequirementMappingOutput.model_validate(
        {
            "implementation_targets": ["chatbot coaching flow"],
            "file_plan": [],
            "quiz_generation_requirements": {
                "quiz_type_count": 0,
                "items_per_type": 0,
                "total_items": 0,
                "required_fields": [],
            },
            "app_constraints": ["정답 설명 대신 질문 개선 코칭"],
            "test_strategy": ["interaction validator"],
        }
    )
    implementation_spec = ImplementationSpec(
        source_path=str(REPO_ROOT / "inputs" / "260428_챗봇"),
        service_name="Question Coaching Chatbot",
        target_framework="streamlit",
        team_identity="교육 서비스 구현 전문 AI Agent 팀",
        service_purpose="되묻기와 진단으로 질문을 개선하는 챗봇",
        target_users=["중학생"],
        learning_goals=["구체성", "맥락성", "목적성"],
        core_features=["need_specificity", "need_context", "need_purpose", "completed"],
        total_count=4,
        items_per_type=0,
        content_interaction_direction=["/api/chat", "awaiting_input", "diagnosing", "completed"],
        excluded_scope=[],
        expected_outputs=["질문 입력 화면", "되묻기 화면", "재요청 결과 화면"],
        acceptance_criteria=["interaction_units가 유효해야 한다."],
        constraints=[],
        content_distribution={
            "need_specificity": 1,
            "need_context": 1,
            "need_purpose": 1,
            "completed": 1,
        },
    )
    content_output = ContentInteractionOutput.model_validate(
        {
            "service_summary": "질문 코칭 챗봇 interaction flow.",
            "interaction_units": [
                {
                    "unit_id": "chat_input",
                    "interaction_type": "free_text_input",
                    "title": "질문 입력",
                    "learner_action": "질문을 입력한다.",
                    "system_response": "입력된 질문을 진단한다.",
                    "input_format": "free_text",
                    "next_step": "chat_feedback",
                    "metadata": {"purpose": "user_input"},
                },
                {
                    "unit_id": "chat_feedback",
                    "interaction_type": "coaching_feedback",
                    "title": "개선 피드백",
                    "system_response": "부족한 요소 하나만 짚어 준다.",
                    "next_step": "END",
                    "metadata": {"diagnosis_criteria": ["구체성", "맥락성", "목적성"]},
                },
            ],
            "flow_notes": ["질문 입력 -> 코칭 피드백"],
        }
    )

    client = ScriptedContentClient(initial_content_output=content_output)
    result = run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )

    assert result.interaction_mode == "coaching"
    assert "content type marker profile" in result.interaction_mode_reason
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True


def test_conflicting_mode_markers_fall_back_to_general_when_units_are_valid() -> None:
    spec_intake_output = SpecIntakeOutput.model_validate(
        {
            "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
            "service_summary": "퀴즈와 챗봇형 되묻기가 섞인 혼합 서비스다.",
            "normalized_requirements": ["객관식 문항", "질문 입력", "되묻기"],
            "delivery_expectations": ["interaction_units 생성"],
            "acceptance_focus": ["general mode에서도 interaction_units 구조가 유효해야 한다."],
        }
    )
    requirement_mapping_output = RequirementMappingOutput.model_validate(
        {
            "implementation_targets": ["hybrid interaction flow"],
            "file_plan": [],
            "quiz_generation_requirements": {
                "quiz_type_count": 0,
                "items_per_type": 0,
                "total_items": 0,
                "required_fields": [],
            },
            "app_constraints": ["multiple interaction styles"],
            "test_strategy": ["interaction validator"],
        }
    )
    implementation_spec = ImplementationSpec(
        source_path=str(REPO_ROOT / "inputs" / "260429_퀘스트_v2"),
        service_name="혼합형 질문 학습 서비스",
        target_framework="streamlit",
        team_identity="교육 서비스 구현 전문 AI Agent 팀",
        service_purpose="퀴즈와 챗봇형 되묻기가 함께 있는 학습 서비스",
        target_users=["중학생"],
        learning_goals=["구체성", "맥락성", "목적성"],
        core_features=["multiple_choice", "diagnosis", "coaching"],
        total_count=0,
        items_per_type=0,
        content_interaction_direction=["문항", "/api/chat", "되묻기"],
        excluded_scope=[],
        expected_outputs=["hybrid demo"],
        acceptance_criteria=["interaction_units가 유효해야 한다."],
        constraints=[],
    )
    content_output = ContentInteractionOutput.model_validate(
        {
            "service_summary": "혼합형 상호작용 구조다.",
            "interaction_units": [
                {
                    "unit_id": "intro",
                    "interaction_type": "display_content",
                    "title": "시작",
                    "system_response": "오늘의 학습 흐름을 안내한다.",
                    "next_step": "ask",
                    "metadata": {"role": "intro"},
                },
                {
                    "unit_id": "ask",
                    "interaction_type": "free_text_input",
                    "title": "질문 입력",
                    "learner_action": "질문을 입력한다.",
                    "input_format": "free_text",
                    "next_step": "feedback",
                    "metadata": {"purpose": "question_input"},
                },
                {
                    "unit_id": "feedback",
                    "interaction_type": "feedback",
                    "title": "결과",
                    "system_response": "입력 결과를 요약한다.",
                    "next_step": "END",
                    "metadata": {"result_type": "summary"},
                },
            ],
            "flow_notes": ["안내 -> 입력 -> 결과"],
        }
    )

    client = ScriptedContentClient(initial_content_output=content_output)
    result = run_content_interaction_agent(
        ContentInteractionInput(
            spec_intake_output=spec_intake_output,
            requirement_mapping_output=requirement_mapping_output,
            implementation_spec=implementation_spec,
        ),
        client,
    )

    assert result.interaction_mode == "general"
    assert "conflicting quiz/coaching markers detected" in result.interaction_mode_reason
    assert result.interaction_validation is not None
    assert result.interaction_validation.structure_valid is True
    assert result.semantic_validation is None
