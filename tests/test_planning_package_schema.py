from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.planning_package import PlanningOutputPackage, PlanningPackage


def build_quiz_payload() -> dict:
    return {
        "service_meta": {
            "service_name": "질문력 향상 퀴즈 서비스",
            "target_user": "중학생",
            "purpose": "질문력 향상을 위한 상호작용형 퀴즈 제공",
            "version": "1.0.0",
        },
        "content_spec": {
            "content_types": [
                "더 좋은 질문 고르기",
                "질문에서 빠진 요소 찾기",
                "모호한 질문 고치기",
                "상황에 맞는 질문 만들기",
            ],
            "total_count": 8,
            "items_per_type": 2,
            "difficulty_levels": ["기초", "적용"],
        },
        "evaluation_spec": {
            "rubric_criteria": ["구체성", "맥락성", "목적성"],
            "grade_levels": ["하", "중", "상"],
            "score_rules": {
                "per_item": 1,
                "bonus": {"all_correct": 2},
            },
        },
        "interaction_spec": {
            "session_structure": ["도입", "문항 풀이", "결과 확인"],
            "state_transitions": ["start->quiz", "quiz->result", "result->retry"],
            "scoring_rules": {
                "show_explanation_after_submit": True,
                "retry_limit": 1,
            },
        },
        "interface_spec": {
            "screens": ["home", "quiz", "result"],
            "api_endpoints": ["/quiz/start", "/quiz/submit"],
        },
        "llm_spec": {
            "generation_prompt": "교육용 퀴즈 문항을 생성한다.",
            "evaluation_prompt": "정답과 학습 포인트를 검토한다.",
        },
        "test_spec": {
            "test_file_path": "tests/test_quiz_service.py",
            "acceptance_criteria": [
                "총 8문항이 생성된다.",
                "4개 유형별로 2문항씩 존재한다.",
            ],
        },
        "constraints": [
            "중학생 수준의 표현을 사용한다.",
            "객관식 문항만 생성한다.",
        ],
    }


@pytest.mark.parametrize(
    "payload",
    [
        build_quiz_payload(),
        {
            "service_meta": {
                "service_name": "영어 단어 복습 서비스",
                "target_user": "초등 고학년",
                "purpose": "반복 복습과 누적 테스트를 통한 어휘 정착",
                "version": "2026.04",
            },
            "content_spec": {
                "content_types": ["단어 카드", "뜻 고르기", "예문 완성"],
                "total_count": 30,
                "items_per_type": 10,
                "difficulty_levels": ["입문", "기초", "도전"],
            },
            "evaluation_spec": {
                "rubric_criteria": ["정확성", "반복 회상", "문맥 이해"],
                "grade_levels": ["starter", "core", "mastery"],
                "score_rules": {"mastery_threshold": 0.85, "streak_bonus": [2, 5]},
            },
            "interaction_spec": {
                "session_structure": ["학습", "자가 테스트", "오답 복습"],
                "state_transitions": ["learn->test", "test->review", "review->learn"],
                "scoring_rules": {"partial_credit": False, "review_weight": 0.5},
            },
            "interface_spec": {
                "screens": ["deck", "test", "review"],
                "api_endpoints": ["/vocab/cards", "/vocab/check"],
            },
            "llm_spec": {
                "generation_prompt": "학년 수준에 맞는 영어 어휘 학습 자료를 생성한다.",
                "evaluation_prompt": "어휘 문항의 오답 원인을 분석한다.",
            },
            "test_spec": {
                "test_file_path": "tests/test_vocab_review.py",
                "acceptance_criteria": [
                    "콘텐츠 유형별 개수가 일치한다.",
                    "오답 복습 플로우가 유지된다.",
                ],
            },
            "constraints": ["교과 수준을 벗어난 단어는 제외한다."],
        },
    ],
)
def test_planning_output_package_accepts_generic_education_services(payload: dict) -> None:
    package = PlanningOutputPackage.model_validate(payload)
    expected = {
        **payload,
        "service_meta": {
            "target_framework": "streamlit",
            **payload["service_meta"],
        },
    }

    assert package.service_meta.service_name
    assert package.service_meta.target_framework == "streamlit"
    assert package.model_dump() == expected


def test_service_meta_accepts_explicit_target_framework() -> None:
    payload = build_quiz_payload()
    payload["service_meta"]["target_framework"] = "react"

    package = PlanningOutputPackage.model_validate(payload)

    assert package.service_meta.target_framework == "react"


def test_planning_package_alias_points_to_same_model() -> None:
    payload = build_quiz_payload()

    canonical = PlanningOutputPackage.model_validate(payload)
    aliased = PlanningPackage.model_validate(payload)

    assert PlanningPackage is PlanningOutputPackage
    assert canonical == aliased


def test_service_name_is_required_and_name_is_rejected() -> None:
    payload = build_quiz_payload()
    payload["service_meta"] = {
        "name": "잘못된 필드명",
        "target_user": "중학생",
        "purpose": "질문력 향상",
        "version": "1.0",
    }

    with pytest.raises(ValidationError) as exc_info:
        PlanningOutputPackage.model_validate(payload)

    message = str(exc_info.value)
    assert "service_name" in message
    assert "name" in message


def test_extra_fields_are_forbidden() -> None:
    payload = build_quiz_payload()
    payload["interface_spec"]["mobile_support"] = True

    with pytest.raises(ValidationError):
        PlanningOutputPackage.model_validate(payload)


def test_rule_dicts_accept_varied_shapes() -> None:
    payload = build_quiz_payload()
    payload["evaluation_spec"]["score_rules"] = {
        "weights": {"specificity": 0.4, "context": 0.3, "purpose": 0.3},
        "bands": [
            {"min": 0, "label": "needs_support"},
            {"min": 80, "label": "proficient"},
        ],
    }
    payload["interaction_spec"]["scoring_rules"] = {
        "per_stage": {"warmup": 1, "challenge": 3},
        "allow_skip": False,
        "metadata": {"source": "teacher_config"},
    }

    package = PlanningOutputPackage.model_validate(payload)

    assert package.evaluation_spec.score_rules["weights"]["specificity"] == 0.4
    assert package.interaction_spec.scoring_rules["per_stage"]["challenge"] == 3


def test_constraints_are_string_list_and_round_trip() -> None:
    payload = build_quiz_payload()

    package = PlanningOutputPackage.model_validate(payload)
    serialized = package.model_dump()
    restored = PlanningOutputPackage.model_validate(serialized)

    assert package.constraints == [
        "중학생 수준의 표현을 사용한다.",
        "객관식 문항만 생성한다.",
    ]
    assert all(isinstance(item, str) for item in restored.constraints)
    assert restored == package
