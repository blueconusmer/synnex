"""Content generation agent for quiz items and learner interaction rules."""

from __future__ import annotations

from clients.llm import LLMClient
from schemas.implementation.content_interaction import (
    ContentInteractionInput,
    ContentInteractionOutput,
)

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


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

    for item in output.items:
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
