from __future__ import annotations

import json
import re

from orchestrator.app_source import build_streamlit_app_source
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.common import QuizItem
from schemas.implementation.prototype_builder import PrototypeBuilderOutput
from schemas.implementation.qa_alignment import QAAlignmentOutput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput

DEFAULT_CONTENT_TYPES = [
    "질문에서 빠진 요소 찾기",
    "더 좋은 질문 고르기",
    "모호한 질문 고치기",
    "상황에 맞는 질문 만들기",
]
DEFAULT_LEARNING_DIMENSIONS = ["구체성", "맥락성", "목적성", "종합성"]


class FakeLLMClient:
    """Deterministic fake client used in automated tests."""

    def generate_json(self, *, prompt: str, response_model, system_prompt: str | None = None):
        response_name = response_model.__name__

        if response_name == SpecIntakeOutput.__name__:
            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Spec Intake Agent",
                        "korean_name": "구현 명세서 분석 Agent",
                    },
                    "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
                    "service_summary": (
                        "중학생의 질문력을 높이기 위한 질문력 향상 퀴즈 서비스 MVP를 구현한다."
                    ),
                    "normalized_requirements": [
                        "질문력 향상 퀴즈 4개 유형을 제공한다.",
                        "각 유형당 2문제씩 총 8문제를 생성한다.",
                        "문제, 선택지, 정답, 해설, 학습 포인트를 포함한다.",
                    ],
                    "delivery_expectations": [
                        "quiz_contents.json 생성",
                        "Streamlit app.py 생성",
                        "QA report와 change log 생성",
                    ],
                    "acceptance_focus": [
                        "총 8문제 생성",
                        "app.py가 quiz_contents.json을 읽음",
                        "실행 로그와 QA 결과가 남음",
                    ],
                }
            )

        if response_name == RequirementMappingOutput.__name__:
            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Requirement Mapping Agent",
                        "korean_name": "구현 요구사항 정리 Agent",
                    },
                    "implementation_targets": [
                        "질문력 향상 퀴즈 콘텐츠 JSON 생성",
                        "Streamlit 기반 퀴즈 MVP 생성",
                        "실행 로그와 QA 문서 생성",
                    ],
                    "file_plan": [
                        {
                            "path": "outputs/quiz_contents.json",
                            "purpose": "Generated quiz content storage",
                            "producing_agent": "Content & Interaction Agent",
                        },
                        {
                            "path": "app.py",
                            "purpose": "Streamlit MVP entrypoint",
                            "producing_agent": "Prototype Builder Agent",
                        },
                    ],
                    "quiz_generation_requirements": {
                        "quiz_type_count": 4,
                        "items_per_type": 2,
                        "total_items": 8,
                        "required_fields": [
                            "question",
                            "choices",
                            "correct_choice",
                            "explanation",
                            "learning_point",
                        ],
                    },
                    "app_constraints": [
                        "app.py는 outputs/quiz_contents.json을 읽는다.",
                        "사용자는 문제 풀이와 채점 결과 확인이 가능해야 한다.",
                    ],
                    "test_strategy": [
                        "py_compile 수행",
                        "Streamlit headless smoke test 수행",
                    ],
                }
            )

        if response_name == ContentInteractionOutput.__name__:
            content_types = _extract_list_from_prompt(prompt, "content_types") or list(
                DEFAULT_CONTENT_TYPES
            )
            learning_dimensions = _extract_list_from_prompt(prompt, "learning_goals") or list(
                DEFAULT_LEARNING_DIMENSIONS
            )
            total_count = _extract_int_from_prompt(prompt, "total_count", default=8)
            service_name = _extract_scalar_from_prompt(prompt, "service_name") or "교육 서비스"

            if (
                content_types == DEFAULT_CONTENT_TYPES
                and learning_dimensions[:3] == ["구체성", "맥락성", "목적성"]
                and total_count == 8
            ):
                return self._build_default_content_output(response_model)

            items = []
            answer_key = {}
            explanations = {}
            learning_points = {}
            for index in range(total_count):
                quiz_type = content_types[index % len(content_types)] if content_types else "generic"
                learning_dimension = (
                    learning_dimensions[index % len(learning_dimensions)]
                    if learning_dimensions
                    else "구체성"
                )
                item_id = f"item-{index + 1:02d}"
                title = f"{quiz_type} {index + 1}"
                question = _build_question_for_type(quiz_type)
                choices = _build_choices_for_type(quiz_type)
                correct = _build_correct_choice_for_type(quiz_type)
                explanation = _build_explanation_for_dimension(learning_dimension)
                learning_point = _build_learning_point_for_dimension(learning_dimension)
                items.append(
                    {
                        "item_id": item_id,
                        "quiz_type": quiz_type,
                        "learning_dimension": learning_dimension,
                        "title": title,
                        "question": question,
                        "choices": choices,
                        "correct_choice": correct,
                        "explanation": explanation,
                        "learning_point": learning_point,
                    }
                )
                answer_key[item_id] = correct
                explanations[item_id] = explanation
                learning_points[item_id] = learning_point

            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Content & Interaction Agent",
                        "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                    },
                    "service_summary": f"{service_name}용 {total_count}문항 콘텐츠다.",
                    "quiz_types": content_types,
                    "items": items,
                    "answer_key": answer_key,
                    "explanations": explanations,
                    "learning_points": learning_points,
                    "interaction_notes": [
                        "사용자는 문제를 순서대로 풀 수 있다.",
                        "채점 후 각 문항의 정답, 해설, 학습 포인트를 확인한다.",
                    ],
                }
            )

        if response_name == QuizItem.__name__:
            item_id_match = re.search(r"유지할 item_id: `([^`]+)`", prompt)
            quiz_type_match = re.search(r"목표 quiz_type: `([^`]+)`", prompt)
            dimension_match = re.search(r"목표 learning_dimension: `([^`]+)`", prompt)
            item_id = item_id_match.group(1) if item_id_match else "quiz-regenerated"
            quiz_type = quiz_type_match.group(1) if quiz_type_match else "더 좋은 질문 고르기"
            learning_dimension = (
                dimension_match.group(1) if dimension_match else "구체성"
            )
            return response_model.model_validate(
                {
                    "item_id": item_id,
                    "quiz_type": quiz_type,
                    "learning_dimension": learning_dimension,
                    "title": f"{quiz_type} 재생성 문항",
                    "question": _build_question_for_type(quiz_type),
                    "choices": _build_choices_for_type(quiz_type),
                    "correct_choice": _build_correct_choice_for_type(quiz_type),
                    "explanation": _build_explanation_for_dimension(learning_dimension),
                    "learning_point": _build_learning_point_for_dimension(learning_dimension),
                }
            )

        if response_name == PrototypeBuilderOutput.__name__:
            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Prototype Builder Agent",
                        "korean_name": "MVP 서비스 코드 생성 Agent",
                    },
                    "service_name": "교육 서비스 MVP",
                    "app_entrypoint": "app.py",
                    "generated_files": [
                        {
                            "path": "app.py",
                            "description": "Self-contained Streamlit quiz MVP",
                            "content": build_streamlit_app_source(
                                "교육 서비스 MVP",
                                "quiz_contents.json",
                            ),
                        }
                    ],
                    "runtime_notes": [
                        "app.py는 outputs/서비스별 콘텐츠 파일을 읽는다.",
                        "streamlit run app.py로 실행한다.",
                    ],
                    "integration_notes": [
                        "콘텐츠 JSON은 app.py와 같은 디렉토리의 outputs 폴더에 있어야 한다."
                    ],
                }
            )

        if response_name == QAAlignmentOutput.__name__:
            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "QA & Alignment Agent",
                        "korean_name": "최종 검수·정합성 확인 Agent",
                    },
                    "alignment_status": "PASS",
                    "qa_checklist": [
                        "configured total_count를 만족하는 문제가 생성되었다.",
                        "모든 문제에 정답과 해설, 학습 포인트가 있다.",
                        "Streamlit MVP가 서비스별 콘텐츠 파일을 읽는다.",
                    ],
                    "qa_issues": [],
                    "change_log_entries": [
                        "Legacy question-power skeleton은 유지하고 active path를 implementation pipeline으로 전환했다.",
                        "Streamlit MVP는 self-contained app.py로 생성되도록 정리했다.",
                    ],
                    "final_summary_points": [
                        "교육 서비스 구현팀 6-Agent 파이프라인이 구성되었다.",
                        "서비스 설정에 맞는 콘텐츠와 Streamlit MVP가 생성되었다.",
                        "실행 로그, QA 리포트, 변경 로그가 남도록 정리되었다.",
                    ],
                }
            )

        raise AssertionError(f"Unexpected response model requested by fake client: {response_name}")

    def _build_default_content_output(self, response_model):
        quiz_types = [
            "질문에서 빠진 요소 찾기",
            "더 좋은 질문 고르기",
            "모호한 질문 고치기",
            "상황에 맞는 질문 만들기",
        ]
        items = []
        answer_key = {}
        explanations = {}
        learning_points = {}
        seed_items = [
                (
                    "quiz-01",
                    quiz_types[0],
                    "빠진 요소 찾기 1",
                    "질문 '이거 왜 그래?'에서 가장 먼저 보완해야 할 요소는 무엇일까?",
                    ["맥락", "색깔", "날짜"],
                    "맥락",
                    "무엇을 묻는지와 어떤 상황인지가 없어서 답하기 어렵다.",
                    "좋은 질문은 상황과 주제를 함께 드러낸다.",
                ),
                (
                    "quiz-02",
                    quiz_types[0],
                    "빠진 요소 찾기 2",
                    "질문 '이 문제 이해가 안 돼.'에서 빠진 핵심 요소는 무엇일까?",
                    ["감정", "구체적인 문제 정보", "필기구 종류"],
                    "구체적인 문제 정보",
                    "어떤 문제인지 말해야 더 정확한 설명을 받을 수 있다.",
                    "구체성이 높아지면 답변의 정확도가 올라간다.",
                ),
                (
                    "quiz-03",
                    quiz_types[1],
                    "더 좋은 질문 고르기 1",
                    "국어 숙제에서 비유를 묻고 싶을 때 더 좋은 질문은 무엇일까?",
                    [
                        "비유가 뭐야?",
                        "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 모르겠어.",
                        "숙제가 많아.",
                    ],
                    "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 모르겠어.",
                    "과목, 문장, 궁금한 이유가 함께 들어 있어 훨씬 구체적이다.",
                    "맥락과 목적이 드러나면 설명이 쉬워진다.",
                ),
                (
                    "quiz-04",
                    quiz_types[1],
                    "더 좋은 질문 고르기 2",
                    "수학 함수 문제를 물을 때 더 좋은 질문은 무엇일까?",
                    [
                        "함수가 어려워.",
                        "중학교 수학 숙제인데 y=2x+1 그래프를 어떻게 그리는지 알려줘.",
                        "수학 왜 배워?",
                    ],
                    "중학교 수학 숙제인데 y=2x+1 그래프를 어떻게 그리는지 알려줘.",
                    "과목, 문제, 도움의 형태가 함께 드러난다.",
                    "목적성까지 포함된 질문이 더 유용하다.",
                ),
                (
                    "quiz-05",
                    quiz_types[2],
                    "모호한 질문 다시 쓰기 1",
                    "다음 중 더 나은 질문으로 고친 것은 무엇일까?",
                    [
                        "이거 설명해 줘.",
                        "과학 시간에 증발이 왜 빨라지는지 실험 결과와 함께 설명해 줘.",
                        "과학은 신기해.",
                    ],
                    "과학 시간에 증발이 왜 빨라지는지 실험 결과와 함께 설명해 줘.",
                    "학습 상황과 원하는 설명의 범위가 분명하다.",
                    "질문을 다시 쓸 때는 상황과 원하는 도움을 함께 적는다.",
                ),
                (
                    "quiz-06",
                    quiz_types[2],
                    "모호한 질문 다시 쓰기 2",
                    "역사 질문을 더 구체적으로 바꾼 것은 무엇일까?",
                    [
                        "왜 그랬어?",
                        "사회 수행평가 준비 중인데 세종대왕이 훈민정음을 만든 이유를 알고 싶어.",
                        "역사는 길어.",
                    ],
                    "사회 수행평가 준비 중인데 세종대왕이 훈민정음을 만든 이유를 알고 싶어.",
                    "상황과 주제가 분명해져서 필요한 설명을 받을 수 있다.",
                    "주제와 목적을 함께 쓰면 질문력이 좋아진다.",
                ),
                (
                    "quiz-07",
                    quiz_types[3],
                    "상황에 맞는 질문 만들기 1",
                    "발표 준비 상황에 맞는 좋은 질문은 무엇일까?",
                    [
                        "이거 알려 줘.",
                        "사회 발표 준비 중인데 플라스틱 사용을 줄이는 방법 예시를 3개 알려줘.",
                        "발표 싫어.",
                    ],
                    "사회 발표 준비 중인데 플라스틱 사용을 줄이는 방법 예시를 3개 알려줘.",
                    "학습 상황과 원하는 산출물 형태가 명확하다.",
                    "상황에 맞는 질문은 결과 형태까지 포함하면 좋다.",
                ),
                (
                    "quiz-08",
                    quiz_types[3],
                    "상황에 맞는 질문 만들기 2",
                    "글쓰기 상황에서 좋은 질문은 무엇일까?",
                    [
                        "도와줘.",
                        "독후감 쓰기 숙제인데 마지막 문단을 어떻게 마무리하면 좋을지 예시를 보여줘.",
                        "글쓰기는 어려워.",
                    ],
                    "독후감 쓰기 숙제인데 마지막 문단을 어떻게 마무리하면 좋을지 예시를 보여줘.",
                    "과제 상황과 원하는 도움의 종류가 모두 드러난다.",
                    "목적이 분명한 질문은 구체적인 도움을 끌어낸다.",
                ),
            ]

        for item_id, quiz_type, title, question, choices, correct, explanation, learning_point in seed_items:
            items.append(
                {
                    "item_id": item_id,
                    "quiz_type": quiz_type,
                    "learning_dimension": (
                        "구체성"
                        if item_id in {"quiz-02"}
                        else "맥락성"
                        if item_id in {"quiz-01", "quiz-03", "quiz-05"}
                        else "목적성"
                    ),
                    "title": title,
                    "question": question,
                    "choices": choices,
                    "correct_choice": correct,
                    "explanation": explanation,
                    "learning_point": learning_point,
                }
            )
            answer_key[item_id] = correct
            explanations[item_id] = explanation
            learning_points[item_id] = learning_point

        return response_model.model_validate(
            {
                "agent": {
                    "english_name": "Content & Interaction Agent",
                    "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                },
                "service_summary": "중학생의 질문력을 높이는 8문항 퀴즈형 MVP 콘텐츠다.",
                "quiz_types": quiz_types,
                "items": items,
                "answer_key": answer_key,
                "explanations": explanations,
                "learning_points": learning_points,
                "interaction_notes": [
                    "사용자는 객관식 문제를 순서대로 풀 수 있다.",
                    "채점 후 각 문항의 정답, 해설, 학습 포인트를 확인한다.",
                ],
            }
        )


def _build_question_for_type(quiz_type: str) -> str:
    if quiz_type == "multiple_choice":
        return "다음 중 더 좋은 질문으로 볼 수 있는 선택지는 무엇일까?"
    if quiz_type == "question_improvement":
        return "모호한 질문을 더 구체적으로 고친 것은 무엇일까?"
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "질문 '이거 왜 그래?'에서 가장 먼저 보완해야 할 빠진 요소는 무엇일까?"
    if quiz_type == "모호한 질문 고치기":
        return "다음 중 모호한 질문을 더 구체적으로 고친 것은 무엇일까?"
    if quiz_type == "상황에 맞는 질문 만들기":
        return "다음 상황에서 가장 적절한 질문은 무엇일까? (과학 발표 준비)"
    return "다음 중 더 좋은 질문은 무엇일까?"


def _build_choices_for_type(quiz_type: str) -> list[str]:
    if quiz_type == "multiple_choice":
        return [
            "이거 뭐야?",
            "과학 숙제인데 증발이 왜 빨라지는지 이유를 알려줘.",
            "과학은 어렵다.",
        ]
    if quiz_type == "question_improvement":
        return [
            "이거 알려 줘.",
            "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해 줘.",
            "비유는 어려워.",
        ]
    if quiz_type == "질문에서 빠진 요소 찾기":
        return ["맥락 정보", "색깔", "느낌"]
    if quiz_type == "모호한 질문 고치기":
        return [
            "이거 알려 줘.",
            "과학 숙제인데 화산이 폭발하는 이유를 단계별로 설명해 줘.",
            "과학은 어렵다.",
        ]
    if quiz_type == "상황에 맞는 질문 만들기":
        return [
            "발표는 왜 해?",
            "과학 발표 준비 중인데 화산이 폭발하는 원인을 한 문장으로 설명해 줄래?",
            "화산은 무섭다.",
        ]
    return [
        "이거 뭐야?",
        "국어 숙제인데 이 문장이 왜 비유인지 예시와 함께 설명해 줘.",
        "숙제가 많아.",
    ]


def _build_correct_choice_for_type(quiz_type: str) -> str:
    if quiz_type == "multiple_choice":
        return "과학 숙제인데 증발이 왜 빨라지는지 이유를 알려줘."
    if quiz_type == "question_improvement":
        return "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해 줘."
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "맥락 정보"
    if quiz_type == "모호한 질문 고치기":
        return "과학 숙제인데 화산이 폭발하는 이유를 단계별로 설명해 줘."
    if quiz_type == "상황에 맞는 질문 만들기":
        return "과학 발표 준비 중인데 화산이 폭발하는 원인을 한 문장으로 설명해 줄래?"
    return "국어 숙제인데 이 문장이 왜 비유인지 예시와 함께 설명해 줘."


def _build_explanation_for_dimension(dimension: str) -> str:
    if dimension == "맥락성":
        return "과목과 학습 상황이 드러나 질문의 맥락성이 높아집니다."
    if dimension == "목적성":
        return "원하는 도움의 형태가 드러나 질문의 목적성이 높아집니다."
    if dimension == "종합성":
        return "상황과 목적, 구체 정보가 함께 드러나 종합성이 높아집니다."
    return "구체적인 조건과 대상이 드러나 질문의 구체성이 높아집니다."


def _build_learning_point_for_dimension(dimension: str) -> str:
    if dimension == "맥락성":
        return "좋은 질문은 과목, 시간, 상황 같은 맥락 정보를 함께 담습니다."
    if dimension == "목적성":
        return "좋은 질문은 어떤 도움을 원하는지 목적을 분명히 씁니다."
    if dimension == "종합성":
        return "좋은 질문은 구체성, 맥락성, 목적성을 함께 고려합니다."
    return "좋은 질문은 대상과 조건을 구체적으로 말합니다."


def _extract_list_from_prompt(prompt: str, field_name: str) -> list[str]:
    match = re.search(rf"- {re.escape(field_name)}: (\[.*?\])", prompt)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return [str(item) for item in payload if str(item).strip()]


def _extract_int_from_prompt(prompt: str, field_name: str, *, default: int) -> int:
    match = re.search(rf"- {re.escape(field_name)}: (\d+)", prompt)
    if not match:
        return default
    return int(match.group(1))


def _extract_scalar_from_prompt(prompt: str, field_name: str) -> str:
    match = re.search(rf"- {re.escape(field_name)}: (.+)", prompt)
    if not match:
        return ""
    return match.group(1).strip()
