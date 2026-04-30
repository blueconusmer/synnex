"""Content generation agent with semantic validation and item-level regeneration."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from clients.llm import LLMClient
from schemas.implementation.common import InteractionUnit, QuizItem
from schemas.implementation.content_interaction import (
    ContentInteractionInput,
    ContentInteractionOutput,
    InteractionValidationSummary,
    SemanticValidationItemResult,
    SemanticValidationSummary,
)

from agents.implementation.helpers import dump_model, dump_optional_model, load_prompt_text, make_label

CANONICAL_QUIZ_TYPES = [
    "더 좋은 질문 고르기",
    "질문에서 빠진 요소 찾기",
    "모호한 질문 고치기",
    "상황에 맞는 질문 만들기",
]
FALLBACK_LEARNING_DIMENSIONS = ["구체성", "맥락성", "목적성", "종합성"]
EXPLICIT_DIMENSION_TERMS = {
    "구체성": ["구체성"],
    "맥락성": ["맥락성"],
    "목적성": ["목적성"],
    "종합성": ["종합성"],
}
SUBJECT_CONTEXT_MARKERS = [
    "국어",
    "수학",
    "과학",
    "사회",
    "역사",
    "실험",
    "수행평가",
    "숙제",
    "발표",
    "프로젝트",
    "글쓰기",
    "독후감",
    "교과",
]
PURPOSE_MARKERS = [
    "알려",
    "설명",
    "예시",
    "도와",
    "도움",
    "방법",
    "원인",
    "이유",
    "어떻게",
    "왜",
    "무엇을",
    "알고 싶",
]
SPECIFICITY_MARKERS = [
    "구체",
    "세부",
    "변인",
    "범위",
    "예시",
    "특정",
    "어떤 문제",
    "문제 내용",
    "10%",
    "20%",
    "30%",
]
DIRECT_DIMENSION_HINTS = {
    "구체성": ["구체", "세부", "변인", "문제 정보", "수치", "범위"],
    "맥락성": ["맥락", "상황", "배경", "과목", "시간", "장소"],
    "목적성": ["목적", "도움", "원하는", "예시", "방법", "설명", "알고 싶", "이유"],
}
QUIZ_MODE_MARKERS = [
    "퀴즈",
    "문항",
    "객관식",
    "정답",
    "점수",
    "배틀",
    "quest",
    "multiple_choice",
    "question_improvement",
    "situation_card",
]
COACHING_MODE_MARKERS = [
    "챗봇",
    "채팅",
    "질문 입력",
    "되묻기",
    "follow_up",
    "coaching",
    "diagnosis",
    "/api/chat",
    "자유 입력",
]
INTERACTION_RESULT_TYPES = {
    "diagnosis",
    "feedback",
    "coaching_feedback",
    "score_summary",
    "next_step_guide",
    "display_content",
}
ORDERED_QUEST_V2_TYPES = [
    "multiple_choice",
    "situation_card",
    "question_improvement",
    "battle",
]


@dataclass
class ItemAssessment:
    item_id: str
    current_quiz_type: str
    expected_quiz_type: str
    quiz_type_match: bool
    current_learning_dimension: str
    expected_learning_dimension: str
    learning_dimension_match: bool
    reasons: list[str] = field(default_factory=list)
    requires_regeneration: bool = False
    applied_label_corrections: list[str] = field(default_factory=list)


def run_content_interaction_agent(
    input_model: ContentInteractionInput,
    llm_client: LLMClient,
) -> ContentInteractionOutput:
    """Generate educational content plus interaction units with quiz backward compatibility."""

    content_types = _resolve_content_types(input_model)
    learning_dimensions = _resolve_learning_dimensions(input_model)
    expected_total = _resolve_expected_total(input_model)
    items_per_type = _resolve_items_per_type(input_model)
    interaction_mode, interaction_mode_reason = _infer_interaction_mode(input_model)
    target_quiz_type_counts = _resolve_target_quiz_type_counts(
        content_types=content_types,
        expected_total=expected_total,
        items_per_type=items_per_type,
        interaction_mode=interaction_mode,
        implementation_spec=input_model.implementation_spec,
    )
    service_name = _resolve_service_name(input_model)

    prompt = load_prompt_text("content_interaction.md").format(
        spec_intake_output=dump_model(input_model.spec_intake_output),
        requirement_mapping_output=dump_model(input_model.requirement_mapping_output),
        service_name=service_name,
        content_types=json.dumps(content_types, ensure_ascii=False),
        learning_goals=json.dumps(learning_dimensions, ensure_ascii=False),
        total_count=expected_total,
        items_per_type=items_per_type,
        content_distribution=json.dumps(target_quiz_type_counts, ensure_ascii=False),
        interaction_mode=interaction_mode,
        interaction_mode_reason=interaction_mode_reason,
        retry_instruction=dump_optional_model(input_model.retry_instruction),
    )
    output = llm_client.generate_json(
        prompt=prompt,
        response_model=ContentInteractionOutput,
        system_prompt=(
            "You generate structured educational content and interaction flows as valid JSON. "
            "Always treat interaction_units as the primary interaction contract."
        ),
    )
    output.agent = make_label(
        "Content & Interaction Agent",
        "교육 콘텐츠·상호작용 생성 Agent",
    )

    output.interaction_mode = interaction_mode
    output.interaction_mode_reason = interaction_mode_reason
    _normalize_interaction_metadata(output)

    if interaction_mode == "quiz":
        _normalize_structural_contract(output)
        summary = _repair_and_validate_content(
            output=output,
            input_model=input_model,
            llm_client=llm_client,
            content_types=content_types,
            learning_dimensions=learning_dimensions,
            expected_total=expected_total,
            target_quiz_type_counts=target_quiz_type_counts,
        )
        output.semantic_validation = summary
        _synchronize_output_maps(output, content_types)
        output.interaction_units = _synthesize_quiz_interaction_units(output.items)
        output.evaluation_rules = _build_quiz_evaluation_rules(
            output=output,
            expected_total=expected_total,
        )
        _validate_content_contract(
            output=output,
            content_types=content_types,
            learning_dimensions=learning_dimensions,
            expected_total=expected_total,
        )
    else:
        output.semantic_validation = None
        output.evaluation_rules = _build_non_quiz_evaluation_rules(
            output=output,
            learning_dimensions=learning_dimensions,
        )

    output.interaction_validation = _validate_interaction_units(
        output=output,
        interaction_mode=interaction_mode,
    )
    return output


def _resolve_content_types(input_model: ContentInteractionInput) -> list[str]:
    implementation_spec = input_model.implementation_spec
    if implementation_spec and implementation_spec.core_features:
        return implementation_spec.core_features
    return list(CANONICAL_QUIZ_TYPES)


def _resolve_learning_dimensions(input_model: ContentInteractionInput) -> list[str]:
    implementation_spec = input_model.implementation_spec
    if implementation_spec and implementation_spec.learning_goals:
        return implementation_spec.learning_goals
    return list(FALLBACK_LEARNING_DIMENSIONS)


def _resolve_expected_total(input_model: ContentInteractionInput) -> int:
    implementation_spec = input_model.implementation_spec
    if implementation_spec and implementation_spec.total_count:
        return implementation_spec.total_count
    return 8


def _resolve_items_per_type(input_model: ContentInteractionInput) -> int:
    implementation_spec = input_model.implementation_spec
    if implementation_spec and implementation_spec.items_per_type:
        return implementation_spec.items_per_type
    return 2


def _resolve_service_name(input_model: ContentInteractionInput) -> str:
    implementation_spec = input_model.implementation_spec
    if implementation_spec and implementation_spec.service_name:
        return implementation_spec.service_name
    return input_model.spec_intake_output.service_summary


def _infer_interaction_mode(input_model: ContentInteractionInput) -> tuple[str, str]:
    implementation_spec = input_model.implementation_spec
    content_types = implementation_spec.core_features if implementation_spec is not None else []
    texts = [
        input_model.spec_intake_output.service_summary,
        *(input_model.spec_intake_output.normalized_requirements or []),
        *(input_model.requirement_mapping_output.implementation_targets or []),
        *(input_model.requirement_mapping_output.app_constraints or []),
    ]
    if implementation_spec is not None:
        texts.extend(
            [
                implementation_spec.service_purpose,
                *implementation_spec.core_features,
                *implementation_spec.content_interaction_direction,
                *implementation_spec.expected_outputs,
            ]
        )

    joined = " ".join(texts).lower()
    content_type_text = " ".join(content_types).lower()
    quiz_hits = _collect_mode_marker_hits(joined, QUIZ_MODE_MARKERS)
    coaching_hits = _collect_mode_marker_hits(joined, COACHING_MODE_MARKERS)
    content_type_quiz_hits = _collect_mode_marker_hits(content_type_text, QUIZ_MODE_MARKERS)

    if quiz_hits and not coaching_hits:
        return "quiz", f"quiz markers detected: {', '.join(quiz_hits[:5])}"
    if coaching_hits and not quiz_hits:
        return "coaching", f"coaching markers detected: {', '.join(coaching_hits[:5])}"
    if coaching_hits and not content_type_quiz_hits:
        return (
            "coaching",
            "coaching markers detected with non-quiz-like content type marker profile: "
            f"coaching={', '.join(coaching_hits[:5])}; quiz={', '.join(quiz_hits[:3]) or 'none'}",
        )
    if quiz_hits and coaching_hits:
        return (
            "general",
            "conflicting quiz/coaching markers detected: "
            f"quiz={', '.join(quiz_hits[:3])}; coaching={', '.join(coaching_hits[:3])}",
        )
    return "general", "no decisive quiz/coaching markers detected; using safe neutral general mode"


def _collect_mode_marker_hits(text: str, markers: list[str]) -> list[str]:
    hits: list[str] = []
    for marker in markers:
        lowered = marker.lower()
        if _text_contains_mode_marker(text, lowered):
            hits.append(marker)
    return hits


def _text_contains_mode_marker(text: str, marker: str) -> bool:
    if re.fullmatch(r"[a-z0-9_/-]+", marker):
        pattern = rf"(?<![a-z0-9_]){re.escape(marker)}(?![a-z0-9_])"
        return re.search(pattern, text) is not None
    return marker in text


def _normalize_interaction_metadata(output: ContentInteractionOutput) -> None:
    if not output.flow_notes and output.interaction_notes:
        output.flow_notes = list(output.interaction_notes)
    if not output.interaction_notes and output.flow_notes:
        output.interaction_notes = list(output.flow_notes)


def _resolve_target_quiz_type_counts(
    *,
    content_types: list[str],
    expected_total: int,
    items_per_type: int,
    interaction_mode: str,
    implementation_spec,
) -> dict[str, int]:
    if interaction_mode != "quiz":
        return {}
    if implementation_spec and implementation_spec.content_distribution:
        return {
            quiz_type: count
            for quiz_type, count in implementation_spec.content_distribution.items()
            if count > 0
        }
    if not content_types:
        return {}
    if len(content_types) == 1:
        return {content_types[0]: expected_total}
    if len(content_types) == 2 and 0 < items_per_type < expected_total:
        return {
            content_types[0]: expected_total - items_per_type,
            content_types[1]: items_per_type,
        }
    return {}


def _repair_and_validate_content(
    *,
    output: ContentInteractionOutput,
    input_model: ContentInteractionInput,
    llm_client: LLMClient,
    content_types: list[str],
    learning_dimensions: list[str],
    expected_total: int,
    target_quiz_type_counts: dict[str, int],
) -> SemanticValidationSummary:
    initial_assessments = [
        _assess_item(item, content_types, learning_dimensions) for item in output.items
    ]

    for item, assessment in zip(output.items, initial_assessments):
        _apply_allowed_label_corrections(item, assessment)

    synthesized_item_ids = _append_missing_quiz_items_if_needed(
        output=output,
        content_types=content_types,
        learning_dimensions=learning_dimensions,
        expected_total=expected_total,
        target_quiz_type_counts=target_quiz_type_counts,
    )
    if synthesized_item_ids:
        _normalize_structural_contract(output)
        initial_assessments = [
            _assess_item(item, content_types, learning_dimensions) for item in output.items
        ]
        for item, assessment in zip(output.items, initial_assessments):
            _apply_allowed_label_corrections(item, assessment)

    regeneration_plan = _plan_regeneration(initial_assessments)
    regeneration_plan.extend(
        _plan_distribution_regeneration(
            items=output.items,
            assessments=initial_assessments,
            target_quiz_type_counts=target_quiz_type_counts,
        )
    )
    regeneration_plan = _deduplicate_regeneration_plan(regeneration_plan)
    regenerated_item_ids: list[str] = list(synthesized_item_ids)

    if regeneration_plan:
        for item_index, target_quiz_type, target_dimension in regeneration_plan:
            original_item = output.items[item_index]
            regenerated_item = _regenerate_item(
                original_item=original_item,
                target_quiz_type=target_quiz_type,
                target_learning_dimension=target_dimension,
                input_model=input_model,
                llm_client=llm_client,
            )
            regenerated_item_ids.append(original_item.item_id)
            output.items[item_index] = regenerated_item

        _normalize_structural_contract(output)

        final_assessments = [
            _assess_item(item, content_types, learning_dimensions) for item in output.items
        ]
        for item, assessment in zip(output.items, final_assessments):
            _apply_allowed_label_corrections(item, assessment)
            if assessment.requires_regeneration:
                raise ValueError(
                    f"Semantic validator failed after regeneration for item {item.item_id}: "
                    + "; ".join(assessment.reasons)
                )
    else:
        final_assessments = [
            _assess_item(item, content_types, learning_dimensions) for item in output.items
        ]

    quiz_type_counts = dict(Counter(item.quiz_type for item in output.items))
    learning_dimension_counts = dict(Counter(item.learning_dimension for item in output.items))
    learning_dimension_values_valid = all(
        item.learning_dimension in learning_dimensions for item in output.items
    )
    quiz_type_distribution_valid = _is_quiz_type_distribution_valid(
        items=output.items,
        content_types=content_types,
        target_quiz_type_counts=target_quiz_type_counts,
    )
    total_count_valid = len(output.items) == expected_total
    semantic_validator_passed = (
        total_count_valid
        and learning_dimension_values_valid
        and quiz_type_distribution_valid
        and not any(assessment.requires_regeneration for assessment in final_assessments)
    )

    if not semantic_validator_passed:
        raise ValueError(
            _build_validation_failure_message(
                assessments=final_assessments,
                quiz_type_counts=quiz_type_counts,
                expected_total=expected_total,
                actual_total=len(output.items),
            )
        )

    return SemanticValidationSummary(
        total_items=len(output.items),
        quiz_type_counts=quiz_type_counts,
        learning_dimension_counts=learning_dimension_counts,
        learning_dimension_values_valid=learning_dimension_values_valid,
        quiz_type_distribution_valid=quiz_type_distribution_valid,
        semantic_validator_passed=semantic_validator_passed,
        regeneration_requested=bool(regenerated_item_ids),
        regeneration_count=len(regenerated_item_ids),
        regenerated_item_ids=regenerated_item_ids,
        item_results=_build_item_results(
            initial_assessments=initial_assessments,
            final_assessments=final_assessments,
            regenerated_item_ids=regenerated_item_ids,
        ),
    )


def _normalize_structural_contract(output: ContentInteractionOutput) -> None:
    fallback_choices = [
        "질문의 상황을 더 자세히 써 보기",
        "도움받고 싶은 내용을 더 분명히 쓰기",
        "예시 문장이나 과목 정보를 추가하기",
        "주제를 더 구체적으로 말하기",
    ]

    for item in output.items:
        if _is_selection_quiz_type(item.quiz_type):
            if item.correct_choice and item.correct_choice not in item.choices:
                item.choices.append(item.correct_choice)
            for fallback in fallback_choices:
                if len(item.choices) >= 3:
                    break
                if fallback not in item.choices:
                    item.choices.append(fallback)
        else:
            item.choices = []

        if item.quiz_type == "multiple_choice" and not item.difficulty:
            item.difficulty = "intro"
        elif item.quiz_type in {"question_improvement", "situation_card"} and not item.difficulty:
            item.difficulty = "main"
        elif item.quiz_type == "battle" and not item.difficulty:
            item.difficulty = "main_advanced"

        if not item.topic_context:
            item.topic_context = item.learning_dimension or "학습 맥락"
        if not item.original_question:
            item.original_question = item.question
        if item.quiz_type == "situation_card" and not item.situation:
            item.situation = item.question or item.topic_context
        if item.quiz_type == "battle":
            if not item.stage_level:
                item.stage_level = "bronze"
            if not item.ai_question:
                item.ai_question = (
                    "국어 수행평가 준비 중인데 비유 표현이 왜 사용되었는지 예시와 함께 설명해줘."
                )
            if not item.situation:
                item.situation = item.question or item.topic_context


def _synthesize_quiz_interaction_units(items: list[QuizItem]) -> list[InteractionUnit]:
    units: list[InteractionUnit] = []
    for item in items:
        action_type = (
            "multiple_choice" if _is_selection_quiz_type(item.quiz_type) else "free_text_input"
        )
        learner_action = item.question
        system_response = item.topic_context or item.learning_dimension
        input_format = "free_text"
        metadata: dict[str, Any] = {
            "source_item_id": item.item_id,
            "quiz_type": item.quiz_type,
            "difficulty": item.difficulty,
            "topic_context": item.topic_context,
            "original_question": item.original_question,
        }
        if action_type == "multiple_choice":
            input_format = "multiple_choice"
            metadata.update(
                {
                    "choices": list(item.choices),
                    "correct_choice": item.correct_choice,
                }
            )
        if item.quiz_type == "situation_card":
            learner_action = item.situation or item.question
            system_response = item.situation or system_response
            metadata["situation"] = item.situation
        if item.quiz_type == "question_improvement":
            learner_action = item.question or "원본 질문을 더 명확하게 다시 써 보세요."
            system_response = item.original_question or system_response
        if item.quiz_type == "battle":
            learner_action = item.question or "AI보다 더 좋은 질문을 작성해 보세요."
            system_response = item.situation or system_response
            metadata.update(
                {
                    "situation": item.situation,
                    "stage_level": item.stage_level,
                    "ai_question": item.ai_question,
                    "battle_rounds": 3,
                    "battle_win_threshold": 2,
                }
            )
        action_unit = InteractionUnit(
            unit_id=f"{item.item_id}_action",
            interaction_type=action_type,
            title=item.title,
            learner_action=learner_action,
            system_response=system_response,
            input_format=input_format,
            feedback_rule=(
                "사용자 응답 후 정답, 해설, 학습 포인트를 포함한 결과 피드백을 보여 준다."
            ),
            learning_dimension=item.learning_dimension,
            metadata=metadata,
        )
        feedback_unit = InteractionUnit(
            unit_id=f"{item.item_id}_feedback",
            interaction_type="feedback",
            title=f"{item.title} 결과",
            learner_action="",
            system_response=item.explanation,
            input_format="",
            feedback_rule="정답, 해설, 학습 포인트를 보여 주고 다음 단계로 이동시킨다.",
            learning_dimension=item.learning_dimension,
            metadata={
                "source_item_id": item.item_id,
                "correct_choice": item.correct_choice,
                "explanation": item.explanation,
                "learning_point": item.learning_point,
                "choices": list(item.choices),
                "quiz_type": item.quiz_type,
                "situation": item.situation,
                "stage_level": item.stage_level,
                "ai_question": item.ai_question,
            },
        )
        units.extend([action_unit, feedback_unit])

        if item.quiz_type == "battle":
            units.append(
                InteractionUnit(
                    unit_id=f"{item.item_id}_battle_final",
                    interaction_type="score_summary",
                    title=f"{item.title} 배틀 결과",
                    learner_action="",
                    system_response="배틀 승패와 보너스 점수를 요약해 보여 준다.",
                    feedback_rule="배틀 종료 후 승패 요약과 다음 세션 결과 진입을 안내한다.",
                    metadata={
                        "source_item_id": item.item_id,
                        "battle_rounds": 3,
                        "battle_win_threshold": 2,
                        "stage_level": item.stage_level,
                    },
                )
            )

    summary_unit = InteractionUnit(
        unit_id="session_summary",
        interaction_type="score_summary",
        title="세션 요약",
        learner_action="",
        system_response="전체 세션 결과와 학습 포인트를 요약해 보여 준다.",
        feedback_rule="세션 종료 시 전체 결과를 요약한다.",
        metadata={"source": "quiz_session"},
        next_step="END",
    )
    units.append(summary_unit)

    for index, unit in enumerate(units):
        if unit.next_step:
            continue
        unit.next_step = units[index + 1].unit_id if index + 1 < len(units) else "END"

    return units


def _append_missing_quiz_items_if_needed(
    *,
    output: ContentInteractionOutput,
    content_types: list[str],
    learning_dimensions: list[str],
    expected_total: int,
    target_quiz_type_counts: dict[str, int],
) -> list[str]:
    synthesized_item_ids: list[str] = []
    current_counts = Counter(item.quiz_type for item in output.items)
    missing_slots = max(expected_total - len(output.items), 0)

    if target_quiz_type_counts and missing_slots > 0:
        for quiz_type, target_count in target_quiz_type_counts.items():
            while current_counts.get(quiz_type, 0) < target_count and missing_slots > 0:
                item_id = f"{quiz_type}_fallback_{current_counts.get(quiz_type, 0) + 1}"
                item = _build_fallback_quiz_item(
                    item_id=item_id,
                    quiz_type=quiz_type,
                    learning_dimension=_select_learning_dimension_for_quiz_type(
                        quiz_type=quiz_type,
                        learning_dimensions=learning_dimensions,
                    ),
                )
                output.items.append(item)
                synthesized_item_ids.append(item_id)
                current_counts[quiz_type] += 1
                missing_slots -= 1

    while missing_slots > 0 and content_types:
        quiz_type = content_types[len(output.items) % len(content_types)]
        item_id = f"{quiz_type}_fallback_{len(output.items) + 1}"
        item = _build_fallback_quiz_item(
            item_id=item_id,
            quiz_type=quiz_type,
            learning_dimension=_select_learning_dimension_for_quiz_type(
                quiz_type=quiz_type,
                learning_dimensions=learning_dimensions,
            ),
        )
        output.items.append(item)
        synthesized_item_ids.append(item_id)
        missing_slots -= 1

    return synthesized_item_ids


def _select_learning_dimension_for_quiz_type(
    *,
    quiz_type: str,
    learning_dimensions: list[str],
) -> str:
    preference_map = {
        "multiple_choice": ["구체성", "맥락성", "목적성", "종합성"],
        "situation_card": ["맥락성", "목적성", "구체성", "종합성"],
        "question_improvement": ["구체성", "목적성", "맥락성", "종합성"],
        "battle": ["종합성", "목적성", "맥락성", "구체성"],
    }
    for candidate in preference_map.get(quiz_type, []):
        if candidate in learning_dimensions:
            return candidate
    return learning_dimensions[0] if learning_dimensions else "구체성"


def _build_fallback_quiz_item(
    *,
    item_id: str,
    quiz_type: str,
    learning_dimension: str,
) -> QuizItem:
    base = {
        "item_id": item_id,
        "quiz_type": quiz_type,
        "learning_dimension": learning_dimension,
        "topic_context": "중학생 학습 상황",
        "explanation": "질문에 주제, 상황, 원하는 답을 함께 넣으면 더 좋은 답변을 받을 수 있어요.",
        "learning_point": "질문력의 핵심 요소를 함께 드러내 보세요.",
    }
    if quiz_type == "multiple_choice":
        return QuizItem(
            **base,
            title="좋은 질문 고르기",
            question="다음 중 AI에게 더 잘 물어본 질문을 고르세요.",
            original_question="설명해줘.",
            choices=[
                "비유가 뭐야?",
                "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해줘.",
                "이거 이해 안 돼.",
                "문학이 어려워.",
            ],
            correct_choice="국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해줘.",
            difficulty="intro",
        )
    if quiz_type == "situation_card":
        return QuizItem(
            **base,
            title="상황 카드",
            question="이 상황에서 AI에게 어떻게 질문할지 작성해 보세요.",
            original_question="도와줘.",
            situation="과학 수행평가 발표를 준비하는 상황",
            correct_choice="",
            choices=[],
            difficulty="main",
        )
    if quiz_type == "battle":
        return QuizItem(
            **base,
            title="배틀 퀘스트",
            question="AI보다 더 좋은 질문을 만들어 보세요.",
            original_question="설명해줘.",
            situation="국어 수행평가에서 비유 표현을 설명해야 하는 상황",
            ai_question="비유가 뭔지 설명해줘.",
            stage_level="bronze",
            correct_choice="",
            choices=[],
            difficulty="main_advanced",
        )
    return QuizItem(
        **base,
        title="질문 개선하기",
        question="이 질문을 더 명확하게 다시 써 보세요.",
        original_question="이거 왜 그래?",
        correct_choice="",
        choices=[],
        difficulty="main",
    )


def _build_quiz_evaluation_rules(
    *,
    output: ContentInteractionOutput,
    expected_total: int,
) -> dict[str, Any]:
    if output.evaluation_rules:
        merged = dict(output.evaluation_rules)
        merged.setdefault("mode", "quiz")
        merged.setdefault("expected_total", expected_total)
        merged.setdefault("feedback_type", "feedback")
        merged.setdefault(
            "feedback_types",
            {
                "feedback": "정답/해설/결과에 대한 일반 피드백",
                "coaching_feedback": "사용자 자유 입력을 바탕으로 개선 방향을 제안하는 코칭형 피드백",
            },
        )
        return merged
    quiz_types = {item.quiz_type for item in output.items}
    rules = {
        "mode": "quiz",
        "expected_total": expected_total,
        "answer_key_mode": "item_id_to_correct_choice",
        "score_policy": {
            "per_item": 1,
            "total_items": expected_total,
        },
        "feedback_type": "feedback",
        "feedback_policy": "정답, 해설, 학습 포인트를 각 문항 결과에서 제공한다.",
        "feedback_types": {
            "feedback": "정답/해설/결과에 대한 일반 피드백",
            "coaching_feedback": "사용자 자유 입력을 바탕으로 개선 방향을 제안하는 코칭형 피드백",
        },
    }
    if "battle" in quiz_types:
        rules.update(
            {
                "battle_rules": {
                    "max_rounds": 3,
                    "win_threshold": 2,
                    "tie_winner": "ai",
                    "win_score": 20,
                    "loss_or_tie_score": 5,
                    "perfect_bonus": 15,
                    "match_bonus": 20,
                },
                "combo_rules": {
                    "scope": "Q2~Q5",
                    "combo_2_bonus": 10,
                    "combo_3_or_more_bonus": 15,
                },
                "grade_rules": {
                    "bronze": {"min_score": 0, "max_score": 99},
                    "silver": {"min_score": 100, "max_score": 299},
                    "gold": {"min_score": 300, "max_score": 599},
                    "platinum": {"min_score": 600, "max_score": None},
                },
            }
        )
    return rules


def _build_non_quiz_evaluation_rules(
    *,
    output: ContentInteractionOutput,
    learning_dimensions: list[str],
) -> dict[str, Any]:
    if output.evaluation_rules:
        merged = dict(output.evaluation_rules)
        merged.setdefault("mode", output.interaction_mode)
        merged.setdefault("diagnosis_criteria", list(learning_dimensions))
        merged.setdefault("completion_rule", "next_step가 END에 도달하면 세션을 종료한다.")
        merged.setdefault(
            "feedback_types",
            {
                "feedback": "정답/해설/결과에 대한 일반 피드백",
                "coaching_feedback": "사용자 자유 입력을 바탕으로 개선 방향을 제안하는 코칭형 피드백",
            },
        )
        return merged
    return {
        "mode": output.interaction_mode,
        "diagnosis_criteria": list(learning_dimensions),
        "feedback_policy": (
            "interaction_units의 learner_action, system_response, feedback_rule을 기준으로 "
            "진단과 후속 피드백을 제공한다."
        ),
        "completion_rule": "next_step가 END에 도달하면 세션을 종료한다.",
        "feedback_types": {
            "feedback": "정답/해설/결과에 대한 일반 피드백",
            "coaching_feedback": "사용자 자유 입력을 바탕으로 개선 방향을 제안하는 코칭형 피드백",
        },
    }


def _synchronize_output_maps(output: ContentInteractionOutput, content_types: list[str]) -> None:
    output.items = _sort_items_for_service_flow(output.items, content_types)
    output.quiz_types = list(content_types)
    output.answer_key = {item.item_id: item.correct_choice for item in output.items}
    output.explanations = {item.item_id: item.explanation for item in output.items}
    output.learning_points = {item.item_id: item.learning_point for item in output.items}


def _sort_items_for_service_flow(
    items: list[QuizItem],
    content_types: list[str],
) -> list[QuizItem]:
    if set(content_types) == set(ORDERED_QUEST_V2_TYPES):
        situation_card_count = 0
        for item in items:
            if item.quiz_type == "multiple_choice":
                item.difficulty = "intro"
            elif item.quiz_type == "question_improvement":
                item.difficulty = "main"
            elif item.quiz_type == "battle":
                item.difficulty = "main_advanced"
            elif item.quiz_type == "situation_card":
                situation_card_count += 1
                item.difficulty = "main" if situation_card_count == 1 else "main_advanced"

        def v2_order(item: QuizItem) -> tuple[int, str]:
            if item.quiz_type == "multiple_choice":
                return (0, item.item_id)
            if item.quiz_type == "situation_card" and item.difficulty == "main":
                return (1, item.item_id)
            if item.quiz_type == "question_improvement":
                return (2, item.item_id)
            if item.quiz_type == "situation_card" and item.difficulty == "main_advanced":
                return (3, item.item_id)
            if item.quiz_type == "battle":
                return (4, item.item_id)
            return (99, item.item_id)

        return sorted(items, key=v2_order)

    if set(content_types) != {"multiple_choice", "question_improvement"}:
        return items

    if not any(item.quiz_type == "multiple_choice" for item in items):
        return items
    if sum(1 for item in items if item.quiz_type == "question_improvement") < 2:
        return items

    ordered = sorted(
        items,
        key=lambda item: (
            0 if item.quiz_type == "multiple_choice" else 1,
            item.item_id,
        ),
    )
    for item in ordered:
        if item.quiz_type == "multiple_choice":
            item.difficulty = "intro"
        elif item.quiz_type == "question_improvement":
            item.difficulty = "main"
    return ordered


def _apply_allowed_label_corrections(item: QuizItem, assessment: ItemAssessment) -> None:
    if item.quiz_type != assessment.expected_quiz_type:
        assessment.applied_label_corrections.append(
            f"quiz_type: {item.quiz_type} -> {assessment.expected_quiz_type}"
        )
        item.quiz_type = assessment.expected_quiz_type
    if item.learning_dimension != assessment.expected_learning_dimension:
        assessment.applied_label_corrections.append(
            "learning_dimension: "
            f"{item.learning_dimension} -> {assessment.expected_learning_dimension}"
        )
        item.learning_dimension = assessment.expected_learning_dimension


def _plan_regeneration(
    assessments: list[ItemAssessment],
) -> list[tuple[int, str, str]]:
    regeneration_targets: list[tuple[int, str, str]] = []
    for index, assessment in enumerate(assessments):
        if assessment.requires_regeneration:
            regeneration_targets.append(
                (
                    index,
                    assessment.expected_quiz_type,
                    assessment.expected_learning_dimension,
                )
            )
    return regeneration_targets


def _plan_distribution_regeneration(
    *,
    items: list[QuizItem],
    assessments: list[ItemAssessment],
    target_quiz_type_counts: dict[str, int],
) -> list[tuple[int, str, str]]:
    if not target_quiz_type_counts:
        return []

    current_counts = Counter(item.quiz_type for item in items)
    deficits = {
        quiz_type: target_count - current_counts.get(quiz_type, 0)
        for quiz_type, target_count in target_quiz_type_counts.items()
        if current_counts.get(quiz_type, 0) < target_count
    }
    surpluses = {
        quiz_type: current_counts.get(quiz_type, 0) - target_count
        for quiz_type, target_count in target_quiz_type_counts.items()
        if current_counts.get(quiz_type, 0) > target_count
    }
    if not deficits or not surpluses:
        return []

    plan: list[tuple[int, str, str]] = []
    reserved_indexes: set[int] = set()
    for target_quiz_type, deficit_count in deficits.items():
        for _ in range(deficit_count):
            candidate_index = _select_surplus_item_index(
                items=items,
                surpluses=surpluses,
                reserved_indexes=reserved_indexes,
            )
            if candidate_index is None:
                return plan
            reserved_indexes.add(candidate_index)
            current_dimension = assessments[candidate_index].expected_learning_dimension
            plan.append(
                (
                    candidate_index,
                    target_quiz_type,
                    current_dimension or items[candidate_index].learning_dimension,
                )
            )
            source_quiz_type = items[candidate_index].quiz_type
            surpluses[source_quiz_type] -= 1
            if surpluses[source_quiz_type] <= 0:
                surpluses.pop(source_quiz_type, None)
    return plan


def _select_surplus_item_index(
    *,
    items: list[QuizItem],
    surpluses: dict[str, int],
    reserved_indexes: set[int],
) -> int | None:
    for index in range(len(items) - 1, -1, -1):
        if index in reserved_indexes:
            continue
        quiz_type = items[index].quiz_type
        if surpluses.get(quiz_type, 0) > 0:
            return index
    return None


def _deduplicate_regeneration_plan(
    plan: list[tuple[int, str, str]],
) -> list[tuple[int, str, str]]:
    by_index: dict[int, tuple[int, str, str]] = {}
    for index, quiz_type, learning_dimension in plan:
        by_index[index] = (index, quiz_type, learning_dimension)
    return [by_index[index] for index in sorted(by_index)]


def _regenerate_item(
    *,
    original_item: QuizItem,
    target_quiz_type: str,
    target_learning_dimension: str,
    input_model: ContentInteractionInput,
    llm_client: LLMClient,
) -> QuizItem:
    prompt = load_prompt_text("regenerate_quiz_item.md").format(
        spec_intake_output=dump_model(input_model.spec_intake_output),
        requirement_mapping_output=dump_model(input_model.requirement_mapping_output),
        current_item=json.dumps(original_item.model_dump(mode="json"), ensure_ascii=False, indent=2),
        target_quiz_type=target_quiz_type,
        target_learning_dimension=target_learning_dimension,
        item_id=original_item.item_id,
    )
    regenerated_item = llm_client.generate_json(
        prompt=prompt,
        response_model=QuizItem,
        system_prompt="You regenerate one educational quiz item as valid JSON only.",
    )
    regenerated_item.item_id = original_item.item_id
    return regenerated_item


def _assess_item(
    item: QuizItem,
    content_types: list[str],
    learning_dimensions: list[str],
) -> ItemAssessment:
    if _supports_action_semantic_validation(content_types):
        expected_quiz_type, quiz_type_reasons = _infer_expected_quiz_type(item)
    else:
        expected_quiz_type, quiz_type_reasons = _infer_configured_quiz_type(item, content_types)

    expected_learning_dimension, learning_reasons = _infer_expected_learning_dimension(
        item,
        learning_dimensions,
    )
    reasons = quiz_type_reasons + learning_reasons
    requires_regeneration = False

    if expected_quiz_type is None:
        expected_quiz_type = (
            item.quiz_type if item.quiz_type in content_types else content_types[0]
            if content_types
            else item.quiz_type
        )
        reasons.append("문항의 quiz_type을 허용된 content_types 안에서 안정적으로 판정할 수 없습니다.")
        requires_regeneration = True

    if content_types and expected_quiz_type not in content_types:
        reasons.append("문항이 implementation_spec.core_features에 정의된 content_types와 맞지 않습니다.")
        requires_regeneration = True

    if expected_learning_dimension is None:
        if item.learning_dimension in learning_dimensions:
            expected_learning_dimension = item.learning_dimension
        elif learning_dimensions:
            expected_learning_dimension = learning_dimensions[0]
        else:
            expected_learning_dimension = item.learning_dimension

    if learning_dimensions and expected_learning_dimension not in learning_dimensions:
        if item.learning_dimension in learning_dimensions:
            expected_learning_dimension = item.learning_dimension
        else:
            expected_learning_dimension = learning_dimensions[0]

    if _supports_action_semantic_validation(content_types) and _has_action_shape_mismatch(
        item,
        expected_quiz_type,
    ):
        reasons.append("문항이 요구하는 행동과 정답/선택지의 형태가 quiz_type 계약과 맞지 않습니다.")
        requires_regeneration = True

    if not _is_question_power_aligned(item):
        reasons.append("해설 또는 학습 포인트가 질문력 향상 목적과 충분히 연결되지 않습니다.")
        requires_regeneration = True

    if _has_explicit_dimension_conflict(item, expected_learning_dimension):
        reasons.append("해설/학습 포인트의 차원 설명이 문항 의미와 충돌합니다.")
        requires_regeneration = True

    return ItemAssessment(
        item_id=item.item_id,
        current_quiz_type=item.quiz_type,
        expected_quiz_type=expected_quiz_type,
        quiz_type_match=item.quiz_type == expected_quiz_type,
        current_learning_dimension=item.learning_dimension,
        expected_learning_dimension=expected_learning_dimension,
        learning_dimension_match=item.learning_dimension == expected_learning_dimension,
        reasons=reasons,
        requires_regeneration=requires_regeneration,
    )


def _supports_action_semantic_validation(content_types: list[str]) -> bool:
    return bool(content_types) and all(quiz_type in CANONICAL_QUIZ_TYPES for quiz_type in content_types)


def _infer_configured_quiz_type(
    item: QuizItem,
    content_types: list[str],
) -> tuple[str | None, list[str]]:
    if not content_types:
        return item.quiz_type, []
    if item.quiz_type in content_types:
        return item.quiz_type, ["문항 quiz_type이 implementation_spec.core_features에 포함됩니다."]
    if "question_improvement" in content_types and _looks_like_question(item.correct_choice):
        return "question_improvement", ["정답 형태가 질문 재작성/생성형이라 question_improvement로 분류합니다."]
    if "multiple_choice" in content_types:
        return "multiple_choice", ["객관식 선택지 구조를 multiple_choice로 분류합니다."]
    return content_types[0], ["허용된 content_types의 첫 값을 기본 fallback으로 사용합니다."]


def _infer_expected_quiz_type(item: QuizItem) -> tuple[str | None, list[str]]:
    question_text = item.question
    title = item.title
    choice_question_count = sum(_looks_like_question(choice) for choice in item.choices)
    correct_is_question = _looks_like_question(item.correct_choice)
    has_original_question_reference = bool(re.search(r"[\"'“”‘’].+?[\"'“”‘’]", question_text))

    scores = {quiz_type: 0 for quiz_type in CANONICAL_QUIZ_TYPES}
    reasons: list[str] = []
    has_explicit_situation_prompt = _contains_any(
        question_text + " " + title,
        ["다음 상황", "상황에서", "상황에 맞는", "상황을 보고", "주어진 상황"],
    )
    has_explicit_rewrite_prompt = _contains_any(
        question_text + " " + title,
        ["고친 것", "다시 쓴", "수정", "바꾼", "모호한 질문", "고쳐", "구체적으로 바꾼"],
    )
    has_explicit_better_prompt = _contains_any(
        question_text + " " + title,
        [
            "더 좋은 질문",
            "더 나은 질문",
            "더 적절한 질문",
            "가장 좋은 질문",
            "개선한 것은",
            "개선된 질문",
        ],
    )

    if has_explicit_situation_prompt:
        scores["상황에 맞는 질문 만들기"] += 4
        reasons.append("질문이 특정 상황에 맞는 질문 생성/선택 행동을 요구합니다.")
    if _contains_any(question_text + " " + title, ["빠진 요소", "누락", "무엇이 부족", "빠진 핵심 요소", "빠진 정보"]):
        scores["질문에서 빠진 요소 찾기"] += 4
        reasons.append("질문이 누락 요소 식별 행동을 요구합니다.")
    if has_explicit_rewrite_prompt:
        scores["모호한 질문 고치기"] += 4
        reasons.append("질문이 기존 질문의 수정/재작성 행동을 요구합니다.")
        if correct_is_question:
            scores["모호한 질문 고치기"] += 2
    if has_explicit_better_prompt:
        scores["더 좋은 질문 고르기"] += 4
        reasons.append("질문이 더 나은 질문을 비교/선택하는 행동을 요구합니다.")

    if correct_is_question and choice_question_count >= 2:
        scores["더 좋은 질문 고르기"] += 2
    if not correct_is_question and choice_question_count <= 1:
        scores["질문에서 빠진 요소 찾기"] += 2
    if has_original_question_reference and correct_is_question:
        scores["모호한 질문 고치기"] += 1
        scores["더 좋은 질문 고르기"] += 1
    if _contains_any(question_text + " " + title, ["가장 적절한 질문", "좋은 질문은 무엇", "질문은 무엇일까"]):
        scores["더 좋은 질문 고르기"] += 1
        if has_explicit_situation_prompt:
            scores["상황에 맞는 질문 만들기"] += 1

    best_quiz_type = max(scores, key=scores.get)
    best_score = scores[best_quiz_type]
    tied_types = [quiz_type for quiz_type, score in scores.items() if score == best_score]
    if best_score <= 0:
        return None, reasons
    if len(tied_types) > 1:
        if "상황에 맞는 질문 만들기" in tied_types and has_explicit_situation_prompt:
            return "상황에 맞는 질문 만들기", reasons
        if "모호한 질문 고치기" in tied_types and has_explicit_rewrite_prompt:
            return "모호한 질문 고치기", reasons
        if "질문에서 빠진 요소 찾기" in tied_types and not correct_is_question:
            return "질문에서 빠진 요소 찾기", reasons
        if "더 좋은 질문 고르기" in tied_types and choice_question_count >= 2:
            return "더 좋은 질문 고르기", reasons
    return best_quiz_type, reasons


def _infer_expected_learning_dimension(
    item: QuizItem,
    allowed_dimensions: list[str],
) -> tuple[str | None, list[str]]:
    question_text = item.question
    correct_choice = item.correct_choice
    explanation = item.explanation
    learning_point = item.learning_point
    rationale_text = f"{explanation} {learning_point}"
    source_text = f"{question_text} {correct_choice}"

    scores = {dimension: 0 for dimension in ["구체성", "맥락성", "목적성"]}
    reasons: list[str] = []

    explicit_dimension = _extract_explicit_dimension(rationale_text)
    if explicit_dimension is not None and (
        not allowed_dimensions or explicit_dimension in allowed_dimensions
    ):
        reasons.append(f"해설 또는 학습 포인트가 {explicit_dimension}을 직접 설명합니다.")
        return explicit_dimension, reasons

    for dimension, markers in DIRECT_DIMENSION_HINTS.items():
        if _contains_any(correct_choice, markers):
            scores[dimension] += 3
        if _contains_any(question_text, markers):
            scores[dimension] += 1
        if _contains_any(rationale_text, markers):
            scores[dimension] += 1

    if _contains_any(source_text, SUBJECT_CONTEXT_MARKERS):
        scores["맥락성"] += 1
    if _contains_any(source_text, PURPOSE_MARKERS):
        scores["목적성"] += 1
    if _contains_any(source_text, SPECIFICITY_MARKERS) or bool(
        re.search(r"\d+%|\d+학년|[\"'“”‘’].+?[\"'“”‘’]", source_text)
    ):
        scores["구체성"] += 1

    sorted_scores = sorted(scores.items(), key=lambda score_item: score_item[1], reverse=True)
    best_dimension, best_score = sorted_scores[0]
    second_score = sorted_scores[1][1]
    if best_score <= 0:
        return None, reasons
    if best_score >= 3 and second_score >= 3 and _contains_any(
        rationale_text,
        ["함께", "여러 요소", "종합", "동시에"],
    ) and (not allowed_dimensions or "종합성" in allowed_dimensions):
        reasons.append("해설 또는 학습 포인트가 여러 질문력 요소의 결합을 설명합니다.")
        return "종합성", reasons
    if allowed_dimensions and best_dimension not in allowed_dimensions:
        return None, reasons
    if best_dimension == "구체성":
        reasons.append("정답이나 질문이 대상/조건/세부 정보를 더 구체적으로 만듭니다.")
    elif best_dimension == "맥락성":
        reasons.append("정답이나 질문이 과목/상황/배경 같은 맥락 정보를 더합니다.")
    else:
        reasons.append("정답이나 질문이 원하는 도움이나 답변 목적을 더 분명하게 만듭니다.")
    return best_dimension, reasons


def _is_question_power_aligned(item: QuizItem) -> bool:
    text = f"{item.explanation} {item.learning_point}"
    return _contains_any(
        text,
        ["질문", "정보", "맥락", "구체", "목적", "상황", "명확", "도움", "답변"],
    )


def _has_action_shape_mismatch(item: QuizItem, expected_quiz_type: str) -> bool:
    question_like_count = sum(_looks_like_question(choice) for choice in item.choices)
    correct_is_question = _looks_like_question(item.correct_choice)
    question_text = item.question

    if expected_quiz_type == "질문에서 빠진 요소 찾기":
        return correct_is_question or question_like_count > 1
    if expected_quiz_type == "더 좋은 질문 고르기":
        return (not correct_is_question) or question_like_count < 2
    if expected_quiz_type == "모호한 질문 고치기":
        return (not correct_is_question) or not _contains_any(
            question_text,
            ["고친", "다시 쓴", "수정", "바꾼", "모호한 질문", "구체적으로"],
        )
    if expected_quiz_type == "상황에 맞는 질문 만들기":
        return (not correct_is_question) or not _contains_any(
            question_text,
            ["다음 상황", "상황에서", "상황에 맞는", "적절한 질문"],
        )
    return False


def _has_explicit_dimension_conflict(item: QuizItem, expected_dimension: str) -> bool:
    if item.quiz_type == "battle":
        return False
    text = f"{item.explanation} {item.learning_point}"
    explicit_dimensions = [
        dimension
        for dimension, terms in EXPLICIT_DIMENSION_TERMS.items()
        if any(term in text for term in terms)
    ]
    if not explicit_dimensions:
        return False
    return any(dimension != expected_dimension for dimension in explicit_dimensions)


def _looks_like_question(text: str) -> bool:
    stripped = text.strip()
    if "?" in stripped:
        return True
    return _contains_any(
        stripped,
        ["무엇", "왜", "어떻게", "어떤", "알려줘", "설명해", "보여줘", "알고 싶", "줄래", "궁금"],
    )


def _contains_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def _extract_explicit_dimension(text: str) -> str | None:
    for dimension, terms in EXPLICIT_DIMENSION_TERMS.items():
        if any(term in text for term in terms):
            return dimension
    return None


def _build_validation_failure_message(
    *,
    assessments: list[ItemAssessment],
    quiz_type_counts: dict[str, int],
    expected_total: int,
    actual_total: int,
) -> str:
    reasons = []
    for assessment in assessments:
        if assessment.requires_regeneration:
            reasons.append(f"{assessment.item_id}: {'; '.join(assessment.reasons)}")
    reasons.append(f"expected_total={expected_total}")
    reasons.append(f"actual_total={actual_total}")
    reasons.append(f"quiz_type_counts={quiz_type_counts}")
    return "Semantic validation failed. " + " | ".join(reasons)


def _is_quiz_type_distribution_valid(
    *,
    items: list[QuizItem],
    content_types: list[str],
    target_quiz_type_counts: dict[str, int],
) -> bool:
    if not content_types or len(set(content_types)) != len(content_types):
        return False
    if not all(item.quiz_type in content_types for item in items):
        return False
    if not target_quiz_type_counts:
        return True

    current_counts = Counter(item.quiz_type for item in items)
    return all(
        current_counts.get(quiz_type, 0) == expected_count
        for quiz_type, expected_count in target_quiz_type_counts.items()
    )


def _build_item_results(
    *,
    initial_assessments: list[ItemAssessment],
    final_assessments: list[ItemAssessment],
    regenerated_item_ids: list[str],
) -> list[SemanticValidationItemResult]:
    final_by_id = {assessment.item_id: assessment for assessment in final_assessments}
    results: list[SemanticValidationItemResult] = []
    for initial in initial_assessments:
        final = final_by_id[initial.item_id]
        reasons = list(dict.fromkeys(initial.reasons + final.reasons))
        results.append(
            SemanticValidationItemResult(
                item_id=initial.item_id,
                current_quiz_type=initial.current_quiz_type,
                expected_quiz_type=final.expected_quiz_type,
                quiz_type_match=initial.current_quiz_type == final.expected_quiz_type,
                current_learning_dimension=initial.current_learning_dimension,
                expected_learning_dimension=final.expected_learning_dimension,
                learning_dimension_match=(
                    initial.current_learning_dimension == final.expected_learning_dimension
                ),
                applied_label_corrections=initial.applied_label_corrections,
                requires_regeneration=initial.item_id in regenerated_item_ids,
                reasons=reasons,
            )
        )
    return results


def _validate_interaction_units(
    *,
    output: ContentInteractionOutput,
    interaction_mode: str,
) -> InteractionValidationSummary:
    issues: list[str] = []
    units = output.interaction_units or []

    if interaction_mode in {"coaching", "general"} and not units:
        issues.append("interaction_units must not be empty for coaching/general mode.")
    if interaction_mode == "quiz" and output.items and not units:
        issues.append("interaction_units must be synthesized or provided for quiz mode.")

    unit_ids = [unit.unit_id for unit in units]
    duplicate_ids = [unit_id for unit_id, count in Counter(unit_ids).items() if count > 1]
    if duplicate_ids:
        issues.append(f"interaction_units contain duplicate unit_id values: {duplicate_ids}.")

    valid_targets = set(unit_ids)
    for unit in units:
        if not unit.interaction_type:
            issues.append(f"{unit.unit_id} is missing interaction_type.")
        if unit.next_step and unit.next_step != "END" and unit.next_step not in valid_targets:
            issues.append(
                f"{unit.unit_id} next_step points to missing unit_id {unit.next_step!r}."
            )
        if unit.interaction_type == "multiple_choice":
            choices = unit.metadata.get("choices")
            correct_choice = unit.metadata.get("correct_choice")
            if not isinstance(choices, list) or not choices:
                issues.append(f"{unit.unit_id} multiple_choice metadata must include choices.")
            if not isinstance(correct_choice, str) or not correct_choice:
                issues.append(
                    f"{unit.unit_id} multiple_choice metadata must include correct_choice."
                )
        if unit.interaction_type == "free_text_input" and not (
            unit.learner_action or unit.input_format
        ):
            issues.append(
                f"{unit.unit_id} free_text_input must describe learner_action or input_format."
            )
        if unit.interaction_type in INTERACTION_RESULT_TYPES and not (
            unit.system_response or unit.metadata
        ):
            issues.append(
                f"{unit.unit_id} {unit.interaction_type} must include system_response or metadata."
            )

    structure_valid = not issues
    if not structure_valid:
        raise ValueError("Interaction-unit validation failed. " + " | ".join(issues))

    return InteractionValidationSummary(
        interaction_mode=interaction_mode,
        mode_inference_reason=output.interaction_mode_reason,
        unit_count=len(units),
        unit_type_counts=dict(Counter(unit.interaction_type for unit in units)),
        structure_valid=structure_valid,
        issues=issues,
    )


def _validate_content_contract(
    *,
    output: ContentInteractionOutput,
    content_types: list[str],
    learning_dimensions: list[str],
    expected_total: int,
) -> None:
    if len(output.quiz_types) != len(content_types):
        raise ValueError(
            f"Expected {len(content_types)} configured quiz types, got {len(output.quiz_types)}."
        )
    if len(output.items) != expected_total:
        raise ValueError(f"Expected {expected_total} quiz items, got {len(output.items)}.")

    for item in output.items:
        if content_types and item.quiz_type not in content_types:
            raise ValueError(
                f"Quiz item {item.item_id} uses unsupported quiz_type {item.quiz_type!r}."
            )
        if learning_dimensions and item.learning_dimension not in learning_dimensions:
            raise ValueError(
                f"Quiz item {item.item_id} uses unsupported learning_dimension "
                f"{item.learning_dimension!r}."
            )
        _validate_item_shape(item)


def _validate_item_shape(item: QuizItem) -> None:
    if _is_selection_quiz_type(item.quiz_type):
        if len(item.choices) < 3:
            raise ValueError(f"Quiz item {item.item_id} must have at least 3 choices.")
        if not item.correct_choice or item.correct_choice not in item.choices:
            raise ValueError(
                f"Quiz item {item.item_id} must include correct_choice inside choices."
            )
        return

    if item.quiz_type == "situation_card":
        if not (item.situation or item.question):
            raise ValueError(
                f"Situation-card item {item.item_id} must include situation or question."
            )
        return

    if item.quiz_type == "question_improvement":
        if not item.original_question:
            raise ValueError(
                f"Question-improvement item {item.item_id} must include original_question."
            )
        return

    if item.quiz_type == "battle":
        if not item.ai_question:
            raise ValueError(f"Battle item {item.item_id} must include ai_question.")
        if not item.stage_level:
            raise ValueError(f"Battle item {item.item_id} must include stage_level.")
        if not (item.situation or item.question):
            raise ValueError(
                f"Battle item {item.item_id} must include situation or question."
            )


def _is_selection_quiz_type(quiz_type: str) -> bool:
    return quiz_type in {
        "multiple_choice",
        "질문에서 빠진 요소 찾기",
        "더 좋은 질문 고르기",
        "모호한 질문 고치기",
        "상황에 맞는 질문 만들기",
    }
