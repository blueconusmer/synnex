"""Content generation agent for quiz items and learner interaction rules."""

from __future__ import annotations

from clients.llm import LLMClient
from schemas.implementation.content_interaction import (
    ContentInteractionInput,
    ContentInteractionOutput,
)

from agents.implementation.helpers import dump_model, load_prompt_text, make_label

CANONICAL_QUIZ_TYPES = [
    "더 좋은 질문 고르기",
    "질문에서 빠진 요소 찾기",
    "모호한 질문 고치기",
    "상황에 맞는 질문 만들기",
]


def run_content_interaction_agent(
    input_model: ContentInteractionInput,
    llm_client: LLMClient,
) -> ContentInteractionOutput:
    """Generate quiz content and interaction notes from the mapped requirements."""

    prompt = load_prompt_text("content_interaction.md").format(
        spec_intake_output=dump_model(input_model.spec_intake_output),
        requirement_mapping_output=dump_model(input_model.requirement_mapping_output),
    )
    output = llm_client.generate_json(
        prompt=prompt,
        response_model=ContentInteractionOutput,
        system_prompt="You generate structured educational quiz content and interaction notes as valid JSON.",
    )
    output.agent = make_label(
        "Content & Interaction Agent",
        "교육 콘텐츠·상호작용 생성 Agent",
    )
    _normalize_content_contract(output)
    _validate_content_contract(output)
    return output


def _normalize_content_contract(output: ContentInteractionOutput) -> None:
    fallback_choices = [
        "질문의 상황을 더 자세히 써 보기",
        "도움받고 싶은 내용을 더 분명히 쓰기",
        "예시 문장이나 과목 정보를 추가하기",
        "주제를 더 구체적으로 말하기",
    ]
    assigned_counts = {quiz_type: 0 for quiz_type in CANONICAL_QUIZ_TYPES}

    for index, item in enumerate(output.items):
        item.learning_dimension = _infer_learning_dimension(item)
        item.quiz_type = _normalize_quiz_type(item, index=index, assigned_counts=assigned_counts)

        if item.correct_choice not in item.choices:
            item.choices.append(item.correct_choice)

        for fallback in fallback_choices:
            if len(item.choices) >= 3:
                break
            if fallback not in item.choices:
                item.choices.append(fallback)

        output.answer_key[item.item_id] = item.correct_choice
        output.explanations[item.item_id] = item.explanation
        output.learning_points[item.item_id] = item.learning_point

    output.quiz_types = list(CANONICAL_QUIZ_TYPES)


def _infer_learning_dimension(item) -> str:
    raw = " ".join(
        [
            item.quiz_type,
            item.title,
            item.question,
            item.explanation,
            item.learning_point,
        ]
    )

    has_specificity = "구체" in raw
    has_context = "맥락" in raw or "상황" in raw or "과목" in raw
    has_purpose = "목적" in raw or "도움" in raw or "원하는" in raw

    if sum([has_specificity, has_context, has_purpose]) >= 2:
        return "종합성"
    if has_specificity:
        return "구체성"
    if has_context:
        return "맥락성"
    if has_purpose:
        return "목적성"

    type_hint = item.quiz_type
    if "구체" in type_hint:
        return "구체성"
    if "맥락" in type_hint:
        return "맥락성"
    if "목적" in type_hint:
        return "목적성"
    return "종합성"


def _normalize_quiz_type(item, *, index: int, assigned_counts: dict[str, int]) -> str:
    raw = " ".join(
        [
            item.quiz_type,
            item.title,
            item.question,
            item.explanation,
            item.learning_point,
        ]
    )

    candidates = [
        ("질문에서 빠진 요소 찾기", ["빠진", "요소"]),
        ("더 좋은 질문 고르기", ["좋은 질문", "고르"]),
        ("모호한 질문 고치기", ["고치", "고쳐", "다시 쓰", "다시 질문", "바꾸"]),
        ("상황에 맞는 질문 만들기", ["상황", "맞는 질문", "만들"]),
    ]

    for quiz_type, keywords in candidates:
        if any(keyword in raw for keyword in keywords) and assigned_counts[quiz_type] < 2:
            assigned_counts[quiz_type] += 1
            return quiz_type

    fallback_quiz_type = CANONICAL_QUIZ_TYPES[(index // 2) % len(CANONICAL_QUIZ_TYPES)]
    if assigned_counts[fallback_quiz_type] < 2:
        assigned_counts[fallback_quiz_type] += 1
        return fallback_quiz_type

    for quiz_type in CANONICAL_QUIZ_TYPES:
        if assigned_counts[quiz_type] < 2:
            assigned_counts[quiz_type] += 1
            return quiz_type

    return fallback_quiz_type


def _validate_content_contract(output: ContentInteractionOutput) -> None:
    quiz_types = set(output.quiz_types)
    if len(quiz_types) != 4:
        raise ValueError(f"Expected 4 quiz types, got {len(quiz_types)}.")
    if len(output.items) != 8:
        raise ValueError(f"Expected 8 quiz items, got {len(output.items)}.")

    type_counts: dict[str, int] = {}
    for item in output.items:
        type_counts[item.quiz_type] = type_counts.get(item.quiz_type, 0) + 1
        if len(item.choices) < 3:
            raise ValueError(f"Quiz item {item.item_id} must have at least 3 choices.")

    for quiz_type in quiz_types:
        if type_counts.get(quiz_type) != 2:
            raise ValueError(f"Quiz type '{quiz_type}' must contain exactly 2 items.")
