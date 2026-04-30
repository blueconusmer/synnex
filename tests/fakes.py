from __future__ import annotations

import json
import re

from orchestrator.app_source import build_streamlit_app_source
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.common import QuizItem
from schemas.implementation.orchestration_decision import OrchestrationJudgeOutput
from schemas.implementation.prototype_builder import AppFlowPlanOutput, AppSourceGenerationOutput
from schemas.implementation.prototype_builder import PrototypeBuilderOutput
from schemas.implementation.qa_alignment import QAAlignmentOutput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.run_test_and_fix import RunTestAndFixOutput
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

    def __init__(
        self,
        *,
        app_source: str | None = None,
        fail_app_generation: bool = False,
        invalid_app_generation: bool = False,
        patch_source: str | None = None,
        repair_sources: list[str] | None = None,
        plan_outputs: list[dict[str, object]] | None = None,
        no_patch: bool = False,
        weak_spec_first_pass: bool = False,
        weak_requirement_first_pass: bool = False,
        invalid_content_first_pass: bool = False,
        judge_target: str = "CONTENT_INTERACTION",
        judge_fail: bool = False,
        judge_invalid_output: bool = False,
    ) -> None:
        self.app_source = app_source
        self.fail_app_generation = fail_app_generation
        self.invalid_app_generation = invalid_app_generation
        self.patch_source = patch_source
        self.repair_sources = list(repair_sources or [])
        self.plan_outputs = list(plan_outputs or [])
        self.no_patch = no_patch
        self.weak_spec_first_pass = weak_spec_first_pass
        self.weak_requirement_first_pass = weak_requirement_first_pass
        self.invalid_content_first_pass = invalid_content_first_pass
        self.judge_target = judge_target
        self.judge_fail = judge_fail
        self.judge_invalid_output = judge_invalid_output
        self.prompts: list[str] = []
        self.response_call_counts: dict[str, int] = {}

    def generate_json(self, *, prompt: str, response_model, system_prompt: str | None = None):
        self.prompts.append(prompt)
        response_name = response_model.__name__
        self.response_call_counts[response_name] = self.response_call_counts.get(response_name, 0) + 1

        if response_name == SpecIntakeOutput.__name__:
            if self.weak_spec_first_pass and not _prompt_has_retry_instruction(prompt):
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Spec Intake Agent",
                            "korean_name": "구현 명세서 분석 Agent",
                        },
                        "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
                        "service_summary": "퀴즈 서비스",
                        "normalized_requirements": [],
                        "delivery_expectations": [],
                        "acceptance_focus": [],
                    }
                )
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
            if self.weak_requirement_first_pass and not _prompt_has_retry_instruction(prompt):
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Requirement Mapping Agent",
                            "korean_name": "구현 요구사항 정리 Agent",
                        },
                        "implementation_targets": [],
                        "file_plan": [],
                        "quiz_generation_requirements": {
                            "quiz_type_count": 0,
                            "items_per_type": 0,
                            "total_items": 0,
                            "required_fields": [],
                        },
                        "app_constraints": [],
                        "test_strategy": [],
                    }
                )
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
            items_per_type = _extract_int_from_prompt(prompt, "items_per_type", default=2)
            service_name = _extract_scalar_from_prompt(prompt, "service_name") or "교육 서비스"
            interaction_mode = _extract_scalar_from_prompt(prompt, "interaction_mode(hint only)") or _extract_scalar_from_prompt(prompt, "interaction_mode") or _infer_fake_interaction_mode(content_types, prompt)
            interaction_mode_reason = (
                "fake deterministic mode inference"
                if interaction_mode != "general"
                else "fake deterministic fallback to general mode"
            )

            if (
                self.invalid_content_first_pass
                and not _prompt_has_retry_instruction(prompt)
                and interaction_mode in {"coaching", "general"}
            ):
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Content & Interaction Agent",
                            "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                        },
                        "service_summary": f"{service_name}용 invalid interaction-unit 콘텐츠다.",
                        "interaction_mode": interaction_mode,
                        "interaction_mode_reason": interaction_mode_reason,
                        "interaction_units": [
                            {
                                "unit_id": "broken_input",
                                "interaction_type": "free_text_input",
                                "title": "질문 입력",
                                "learner_action": "학습자가 질문을 입력한다.",
                                "system_response": "질문을 입력해 보세요.",
                                "input_format": "free_text",
                                "feedback_rule": "",
                                "learning_dimension": "",
                                "next_step": "END",
                                "metadata": {},
                            }
                        ],
                        "flow_notes": [],
                        "evaluation_rules": {},
                        "interaction_notes": [],
                    }
                )

            if (
                content_types == DEFAULT_CONTENT_TYPES
                and learning_dimensions[:3] == ["구체성", "맥락성", "목적성"]
                and total_count == 8
            ):
                return self._build_default_content_output(response_model)

            if interaction_mode in {"coaching", "general"} and not _looks_like_quiz_content_types(content_types):
                interaction_units = _build_non_quiz_interaction_units(
                    service_name=service_name,
                    learning_dimensions=learning_dimensions,
                )
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Content & Interaction Agent",
                            "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                        },
                        "service_summary": f"{service_name}용 interaction-unit 중심 콘텐츠다.",
                        "interaction_mode": interaction_mode,
                        "interaction_mode_reason": interaction_mode_reason,
                        "interaction_units": interaction_units,
                        "flow_notes": [
                            "사용자는 자유 입력을 하고 진단 결과를 본 뒤 다음 행동을 안내받는다.",
                        ],
                        "evaluation_rules": {
                            "mode": interaction_mode,
                            "diagnosis_criteria": learning_dimensions,
                            "feedback_policy": "사용자 자유 입력을 기반으로 개선 방향을 제안한다.",
                        },
                        "interaction_notes": [
                            "interaction_units를 primary contract로 사용한다.",
                        ],
                    }
                )

            items = []
            answer_key = {}
            explanations = {}
            learning_points = {}
            quiz_type_sequence = _build_quiz_type_sequence(
                content_types,
                total_count=total_count,
                items_per_type=items_per_type,
            )
            for index, quiz_type in enumerate(quiz_type_sequence):
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
                        "difficulty": _difficulty_for_type(quiz_type, index=index),
                        "learning_dimension": learning_dimension,
                        "title": title,
                        "topic_context": _build_topic_context_for_type(quiz_type),
                        "situation": _build_situation_for_type(quiz_type),
                        "original_question": _build_original_question_for_type(quiz_type),
                        "stage_level": _build_stage_level_for_type(quiz_type),
                        "question": question,
                        "choices": choices,
                        "correct_choice": correct,
                        "explanation": explanation,
                        "learning_point": learning_point,
                        "ai_question": _build_ai_question_for_type(quiz_type),
                    }
                )
                answer_key[item_id] = correct
                explanations[item_id] = explanation
                learning_points[item_id] = learning_point

            interaction_units = _build_quiz_interaction_units_from_items(items)

            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Content & Interaction Agent",
                        "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                    },
                    "service_summary": f"{service_name}용 {total_count}문항 콘텐츠다.",
                    "interaction_mode": interaction_mode,
                    "interaction_mode_reason": interaction_mode_reason,
                    "quiz_types": content_types,
                    "items": items,
                    "answer_key": answer_key,
                    "explanations": explanations,
                    "learning_points": learning_points,
                    "interaction_notes": [
                        "사용자는 문제를 순서대로 풀 수 있다.",
                        "채점 후 각 문항의 정답, 해설, 학습 포인트를 확인한다.",
                    ],
                    "interaction_units": interaction_units,
                    "flow_notes": [
                        "interaction_units의 순서와 next_step에 따라 화면 흐름을 구성한다.",
                    ],
                    "evaluation_rules": _build_evaluation_rules_for_content_types(
                        content_types=content_types,
                        total_count=total_count,
                    ),
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
                    "difficulty": _difficulty_for_type(quiz_type),
                    "learning_dimension": learning_dimension,
                    "title": f"{quiz_type} 재생성 문항",
                    "topic_context": _build_topic_context_for_type(quiz_type),
                    "situation": _build_situation_for_type(quiz_type),
                    "original_question": _build_original_question_for_type(quiz_type),
                    "stage_level": _build_stage_level_for_type(quiz_type),
                    "question": _build_question_for_type(quiz_type),
                    "choices": _build_choices_for_type(quiz_type),
                    "correct_choice": _build_correct_choice_for_type(quiz_type),
                    "explanation": _build_explanation_for_dimension(learning_dimension),
                    "learning_point": _build_learning_point_for_dimension(learning_dimension),
                    "ai_question": _build_ai_question_for_type(quiz_type),
                }
            )

        if response_name == AppFlowPlanOutput.__name__:
            if self.plan_outputs:
                return response_model.model_validate(self.plan_outputs.pop(0))
            return response_model.model_validate(_build_fake_app_flow_plan_from_prompt(prompt))

        if response_name == AppSourceGenerationOutput.__name__:
            if self.fail_app_generation:
                raise RuntimeError("fake app generation failure")
            content_filename = _extract_scalar_from_prompt(prompt, "content_filename") or "quiz_contents.json"
            if self.invalid_app_generation:
                return response_model.model_validate(
                    {
                        "app_path": "app.py",
                        "app_source": "print('not a streamlit app')",
                        "generation_notes": ["invalid app source for fallback test"],
                    }
                )
            default_source = (
                _build_coaching_llm_generated_streamlit_source(content_filename)
                if _prompt_requires_coaching_builder_contract(prompt)
                else _build_quest_v2_llm_generated_streamlit_source(content_filename)
                if _prompt_requires_v2_builder_contract(prompt)
                else _build_llm_generated_streamlit_source(content_filename)
            )
            is_repair_prompt = "The previous generated app.py failed validation." in prompt
            repair_source = None
            if is_repair_prompt and self.repair_sources:
                repair_source = self.repair_sources.pop(0)
            elif is_repair_prompt and self.patch_source is not None:
                repair_source = self.patch_source
            return response_model.model_validate(
                {
                    "app_path": "app.py",
                    "app_source": repair_source or self.app_source or default_source,
                    "generation_notes": ["fake LLM generated deterministic Streamlit app.py"],
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

        if response_name == RunTestAndFixOutput.__name__:
            if self.no_patch:
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Run Test And Fix Agent",
                            "korean_name": "실행·테스트·수정 Agent",
                        },
                        "checks_run": ["py_compile"],
                        "failures": [
                            {
                                "check_name": "py_compile",
                                "summary": "py_compile failed",
                                "details": "fake failure",
                            }
                        ],
                        "fixes_applied": [],
                        "remaining_risks": ["No deterministic patch was provided."],
                        "patched_files": [],
                        "should_retry_builder": False,
                    }
                )
            return response_model.model_validate(
                {
                    "agent": {
                        "english_name": "Run Test And Fix Agent",
                        "korean_name": "실행·테스트·수정 Agent",
                    },
                    "checks_run": ["py_compile"],
                    "failures": [
                        {
                            "check_name": "py_compile",
                            "summary": "py_compile failed",
                            "details": "fake failure",
                        }
                    ],
                    "fixes_applied": ["Applied minimal app.py syntax patch."],
                    "remaining_risks": [],
                    "patched_files": [
                        {
                            "path": "app.py",
                            "reason": "Fix generated app syntax error.",
                            "content": self.patch_source
                            or _build_llm_generated_streamlit_source("quiz_contents.json"),
                        }
                    ],
                    "should_retry_builder": True,
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

        if response_name == OrchestrationJudgeOutput.__name__:
            if self.judge_fail:
                raise RuntimeError("fake orchestration judge failure")
            if self.judge_invalid_output:
                return response_model.model_validate(
                    {
                        "chosen_target_agent": "PROTOTYPE_BUILDER",
                        "reason": "invalid target for fallback test",
                        "retry_instruction": {
                            "summary": "invalid",
                            "must_fix": [],
                            "evidence": [],
                            "preserve_constraints": [],
                        },
                        "confidence_note": "invalid target",
                    }
                )
            return response_model.model_validate(
                {
                    "chosen_target_agent": self.judge_target,
                    "reason": "fake deterministic orchestration judge choice",
                    "retry_instruction": {
                        "summary": f"{self.judge_target}로 upstream contract를 보강한다.",
                        "must_fix": [
                            "interaction flow 또는 app constraints를 더 명확히 보강하라."
                        ],
                        "evidence": ["fake judge evidence"],
                        "preserve_constraints": ["target_framework=streamlit"],
                    },
                    "confidence_note": "deterministic fake judge output",
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
                    "difficulty": (
                        "intro"
                        if quiz_type in {"질문에서 빠진 요소 찾기", "더 좋은 질문 고르기"}
                        else "main"
                    ),
                    "learning_dimension": (
                        "구체성"
                        if item_id in {"quiz-02"}
                        else "맥락성"
                        if item_id in {"quiz-01", "quiz-03", "quiz-05"}
                        else "목적성"
                    ),
                    "title": title,
                    "topic_context": _build_topic_context_for_type(quiz_type),
                    "situation": _build_situation_for_type(quiz_type),
                    "original_question": _build_original_question_for_type(quiz_type),
                    "stage_level": _build_stage_level_for_type(quiz_type),
                    "question": question,
                    "choices": choices,
                    "correct_choice": correct,
                    "explanation": explanation,
                    "learning_point": learning_point,
                    "ai_question": _build_ai_question_for_type(quiz_type),
                }
            )
            answer_key[item_id] = correct
            explanations[item_id] = explanation
            learning_points[item_id] = learning_point

        interaction_units = _build_quiz_interaction_units_from_items(items)

        return response_model.model_validate(
            {
                "agent": {
                    "english_name": "Content & Interaction Agent",
                    "korean_name": "교육 콘텐츠·상호작용 생성 Agent",
                },
                "service_summary": "중학생의 질문력을 높이는 8문항 퀴즈형 MVP 콘텐츠다.",
                "interaction_mode": "quiz",
                "interaction_mode_reason": "fake deterministic mode inference",
                "quiz_types": quiz_types,
                "items": items,
                "answer_key": answer_key,
                "explanations": explanations,
                "learning_points": learning_points,
                "interaction_notes": [
                    "사용자는 객관식 문제를 순서대로 풀 수 있다.",
                    "채점 후 각 문항의 정답, 해설, 학습 포인트를 확인한다.",
                ],
                "interaction_units": interaction_units,
                "flow_notes": [
                    "interaction_units의 순서와 next_step에 따라 문제 풀이와 결과 화면이 이어진다.",
                ],
                "evaluation_rules": _build_evaluation_rules_for_content_types(
                    content_types=quiz_types,
                    total_count=8,
                ),
            }
        )


def _build_question_for_type(quiz_type: str) -> str:
    if quiz_type == "multiple_choice":
        return "다음 중 더 좋은 질문으로 볼 수 있는 선택지는 무엇일까?"
    if quiz_type == "situation_card":
        return "이 상황에서 AI에게 어떤 질문을 하면 가장 도움이 될까?"
    if quiz_type == "question_improvement":
        return "원본 질문을 더 구체적이고 도움받기 쉬운 질문으로 다시 써보세요."
    if quiz_type == "battle":
        return "AI보다 더 좋은 질문을 만들어 배틀에서 이겨 보세요."
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "질문 '이거 왜 그래?'에서 가장 먼저 보완해야 할 빠진 요소는 무엇일까?"
    if quiz_type == "모호한 질문 고치기":
        return "다음 중 모호한 질문을 더 구체적으로 고친 것은 무엇일까?"
    if quiz_type == "상황에 맞는 질문 만들기":
        return "다음 상황에서 가장 적절한 질문은 무엇일까? (과학 발표 준비)"
    return "다음 중 더 좋은 질문은 무엇일까?"


def _prompt_has_retry_instruction(prompt: str) -> bool:
    if "Retry context:" not in prompt:
        return False
    return "Retry context:\n없음" not in prompt and "Retry context:\r\n없음" not in prompt


def _infer_fake_interaction_mode(content_types: list[str], prompt: str) -> str:
    lowered = prompt.lower()
    if any(marker in lowered for marker in ["/api/chat", "coaching", "되묻기", "챗봇"]):
        return "coaching"
    if _looks_like_quiz_content_types(content_types):
        return "quiz"
    return "general"


def _looks_like_quiz_content_types(content_types: list[str]) -> bool:
    quiz_markers = {
        "multiple_choice",
        "situation_card",
        "question_improvement",
        "battle",
        "질문에서 빠진 요소 찾기",
        "더 좋은 질문 고르기",
        "모호한 질문 고치기",
        "상황에 맞는 질문 만들기",
    }
    return bool(content_types) and all(content_type in quiz_markers for content_type in content_types)


def _build_quiz_interaction_units_from_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    for item in items:
        item_id = str(item["item_id"])
        quiz_type = str(item["quiz_type"])
        action_type = (
            "multiple_choice" if quiz_type == "multiple_choice" else "free_text_input"
        )
        learner_action = item["question"]
        system_response = item["topic_context"]
        if quiz_type == "situation_card":
            learner_action = item.get("question") or item.get("situation") or ""
            system_response = item.get("situation") or item["topic_context"]
        elif quiz_type == "question_improvement":
            system_response = item.get("original_question") or item["topic_context"]
        elif quiz_type == "battle":
            learner_action = item.get("question") or "AI보다 더 좋은 질문을 만들어 보세요."
            system_response = item.get("situation") or item["topic_context"]
        units.append(
            {
                "unit_id": f"{item_id}_action",
                "interaction_type": action_type,
                "title": item["title"],
                "learner_action": learner_action,
                "system_response": system_response,
                "input_format": "free_text" if action_type == "free_text_input" else "multiple_choice",
                "feedback_rule": "응답 후 결과 피드백을 제공한다.",
                "learning_dimension": item["learning_dimension"],
                "next_step": f"{item_id}_feedback",
                "metadata": {
                    "source_item_id": item_id,
                    "quiz_type": quiz_type,
                    "choices": list(item["choices"]),
                    "correct_choice": item["correct_choice"],
                    "difficulty": item["difficulty"],
                    "topic_context": item["topic_context"],
                    "original_question": item["original_question"],
                    "situation": item.get("situation", ""),
                    "stage_level": item.get("stage_level", ""),
                    "ai_question": item.get("ai_question", ""),
                },
            }
        )
        units.append(
            {
                "unit_id": f"{item_id}_feedback",
                "interaction_type": "feedback",
                "title": f"{item['title']} 결과",
                "learner_action": "",
                "system_response": item["explanation"],
                "input_format": "",
                "feedback_rule": "정답, 해설, 학습 포인트를 보여 준다.",
                "learning_dimension": item["learning_dimension"],
                "next_step": "",
                "metadata": {
                    "source_item_id": item_id,
                    "choices": list(item["choices"]),
                    "correct_choice": item["correct_choice"],
                    "explanation": item["explanation"],
                    "learning_point": item["learning_point"],
                    "quiz_type": quiz_type,
                    "situation": item.get("situation", ""),
                    "stage_level": item.get("stage_level", ""),
                    "ai_question": item.get("ai_question", ""),
                },
            }
        )

        if quiz_type == "battle":
            units.append(
                {
                    "unit_id": f"{item_id}_battle_final",
                    "interaction_type": "score_summary",
                    "title": f"{item['title']} 배틀 결과",
                    "learner_action": "",
                    "system_response": "배틀 승패와 보너스 점수를 요약한다.",
                    "input_format": "",
                    "feedback_rule": "배틀 종료 후 최종 결과를 보여 준다.",
                    "learning_dimension": item["learning_dimension"],
                    "next_step": "",
                    "metadata": {
                        "source_item_id": item_id,
                        "battle_rounds": 3,
                        "battle_win_threshold": 2,
                        "stage_level": item.get("stage_level", ""),
                    },
                }
            )

    units.append(
        {
            "unit_id": "session_summary",
            "interaction_type": "score_summary",
            "title": "세션 요약",
            "learner_action": "",
            "system_response": "전체 점수와 학습 포인트를 요약한다.",
            "input_format": "",
            "feedback_rule": "세션 종료 시 전체 결과를 요약한다.",
            "learning_dimension": "",
            "next_step": "END",
            "metadata": {"source": "fake_quiz_session"},
        }
    )

    for index, unit in enumerate(units):
        if unit["next_step"]:
            continue
        unit["next_step"] = units[index + 1]["unit_id"] if index + 1 < len(units) else "END"
    return units


def _build_non_quiz_interaction_units(
    *,
    service_name: str,
    learning_dimensions: list[str],
) -> list[dict[str, object]]:
    primary_dimension = learning_dimensions[0] if learning_dimensions else "구체성"
    return [
        {
            "unit_id": "chat_input",
            "interaction_type": "free_text_input",
            "title": f"{service_name} 질문 입력",
            "learner_action": "학습자가 현재 질문이나 고민을 자유롭게 입력한다.",
            "system_response": "질문을 입력하면 진단을 시작한다.",
            "input_format": "free_text",
            "feedback_rule": "입력 후 diagnosis 단계로 이동한다.",
            "learning_dimension": primary_dimension,
            "next_step": "chat_diagnosis",
            "metadata": {"purpose": "user_question_input"},
        },
        {
            "unit_id": "chat_diagnosis",
            "interaction_type": "diagnosis",
            "title": "질문 진단",
            "learner_action": "",
            "system_response": "질문의 구체성, 맥락성, 목적성을 간단히 진단한다.",
            "input_format": "",
            "feedback_rule": "진단 기준을 바탕으로 coaching_feedback으로 이동한다.",
            "learning_dimension": primary_dimension,
            "next_step": "chat_feedback",
            "metadata": {"diagnosis_criteria": learning_dimensions},
        },
        {
            "unit_id": "chat_feedback",
            "interaction_type": "coaching_feedback",
            "title": "개선 피드백",
            "learner_action": "",
            "system_response": "사용자 자유 입력을 바탕으로 더 좋은 질문 방향을 제안한다.",
            "input_format": "",
            "feedback_rule": "coaching feedback을 제공한 뒤 다음 행동을 안내한다.",
            "learning_dimension": primary_dimension,
            "next_step": "next_step_guide",
            "metadata": {"feedback_scope": "question_improvement"},
        },
        {
            "unit_id": "next_step_guide",
            "interaction_type": "next_step_guide",
            "title": "다음 단계 안내",
            "learner_action": "",
            "system_response": "개선된 질문을 다시 입력하거나 세션을 종료할 수 있다.",
            "input_format": "",
            "feedback_rule": "세션 종료 또는 재입력을 안내한다.",
            "learning_dimension": primary_dimension,
            "next_step": "END",
            "metadata": {"completion": "guided"},
        },
    ]


def _build_choices_for_type(quiz_type: str) -> list[str]:
    if quiz_type == "multiple_choice":
        return [
            "이거 뭐야?",
            "과학 숙제인데 증발이 왜 빨라지는지 이유를 알려줘.",
            "과학은 어렵다.",
        ]
    if quiz_type in {"situation_card", "battle"}:
        return []
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
    if quiz_type == "situation_card":
        return "국어 발표 준비 중인데 비유 표현이 왜 쓰였는지 예시와 함께 설명해줘."
    if quiz_type == "question_improvement":
        return "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해 줘."
    if quiz_type == "battle":
        return "수행평가 준비 중인데 비유 표현의 효과를 예시와 함께 비교 설명해줘."
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "맥락 정보"
    if quiz_type == "모호한 질문 고치기":
        return "과학 숙제인데 화산이 폭발하는 이유를 단계별로 설명해 줘."
    if quiz_type == "상황에 맞는 질문 만들기":
        return "과학 발표 준비 중인데 화산이 폭발하는 원인을 한 문장으로 설명해 줄래?"
    return "국어 숙제인데 이 문장이 왜 비유인지 예시와 함께 설명해 줘."


def _build_topic_context_for_type(quiz_type: str) -> str:
    if quiz_type == "multiple_choice":
        return "국어 비유 표현 학습"
    if quiz_type == "situation_card":
        return "국어 수행평가 상황 카드"
    if quiz_type == "question_improvement":
        return "수학 일차방정식"
    if quiz_type == "battle":
        return "국어 질문 배틀"
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "과학 발표 준비"
    if quiz_type == "모호한 질문 고치기":
        return "사회 수행평가 준비"
    if quiz_type == "상황에 맞는 질문 만들기":
        return "글쓰기 과제"
    return "학습 맥락"


def _build_original_question_for_type(quiz_type: str) -> str:
    if quiz_type == "multiple_choice":
        return "비유가 뭔지 모르겠어"
    if quiz_type == "situation_card":
        return "이 상황에서 뭐라고 물어봐야 하지?"
    if quiz_type == "question_improvement":
        return "이거 어떻게 풀어"
    if quiz_type == "battle":
        return "좋은 질문을 만들고 싶어"
    if quiz_type == "질문에서 빠진 요소 찾기":
        return "이거 왜 그래?"
    if quiz_type == "모호한 질문 고치기":
        return "왜 그랬어?"
    if quiz_type == "상황에 맞는 질문 만들기":
        return "도와줘."
    return "이거 알려 줘."


def _build_quiz_type_sequence(
    content_types: list[str],
    *,
    total_count: int,
    items_per_type: int,
) -> list[str]:
    if (
        content_types == ["multiple_choice", "question_improvement"]
        and total_count == 3
        and items_per_type == 2
    ):
        return ["multiple_choice", "question_improvement", "question_improvement"]
    if (
        content_types == ["multiple_choice", "situation_card", "question_improvement", "battle"]
        and total_count == 5
    ):
        return [
            "multiple_choice",
            "situation_card",
            "question_improvement",
            "situation_card",
            "battle",
        ]

    if not content_types:
        return ["generic"] * total_count
    return [content_types[index % len(content_types)] for index in range(total_count)]


def _build_situation_for_type(quiz_type: str) -> str:
    if quiz_type == "situation_card":
        return "국어 수행평가 준비 중이고, 비유 표현을 이해해 발표해야 한다."
    if quiz_type == "battle":
        return "AI보다 더 좋은 질문을 만들어 발표 준비 상황을 해결해야 한다."
    return ""


def _build_stage_level_for_type(quiz_type: str) -> str:
    if quiz_type == "battle":
        return "silver"
    return ""


def _build_ai_question_for_type(quiz_type: str) -> str:
    if quiz_type == "battle":
        return "국어 수행평가 준비 중인데 비유 표현의 효과를 예시와 함께 설명해줘."
    return ""


def _difficulty_for_type(quiz_type: str, *, index: int | None = None) -> str:
    if quiz_type == "multiple_choice":
        return "intro"
    if quiz_type == "question_improvement":
        return "main"
    if quiz_type == "situation_card":
        if index is not None and index >= 3:
            return "main_advanced"
        return "main"
    if quiz_type == "battle":
        return "main_advanced"
    return "main"


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


def _build_evaluation_rules_for_content_types(
    *,
    content_types: list[str],
    total_count: int,
) -> dict[str, object]:
    rules: dict[str, object] = {
        "mode": "quiz",
        "score_policy": {"per_item": 1, "total_items": total_count},
        "feedback_type": "feedback",
    }
    if "battle" in content_types:
        rules.update(
            {
                "combo_rules": {"combo_2_bonus": 10, "combo_3_or_more_bonus": 15},
                "battle_rules": {
                    "max_rounds": 3,
                    "win_threshold": 2,
                    "tie_winner": "ai",
                    "win_score": 20,
                    "loss_or_tie_score": 5,
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


def _extract_list_from_prompt(prompt: str, field_name: str) -> list[str]:
    prefix = f"- {field_name}: "
    for line in prompt.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        payload_text = stripped[len(prefix) :].strip()
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in payload if str(item).strip()]
    return []


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


def _build_fake_app_flow_plan_from_prompt(prompt: str) -> dict[str, object]:
    interaction_mode = _extract_scalar_from_prompt(prompt, "interaction_mode") or "quiz"
    content_runtime_source = (
        _extract_scalar_from_prompt(prompt, "expected_content_runtime_source") or "quests"
    )
    required_screen_constants = _extract_list_from_prompt(prompt, "required_screen_constants")
    required_transition_assignments = _extract_list_from_prompt(
        prompt,
        "required_transition_assignments",
    )
    required_functions = _extract_list_from_prompt(prompt, "required_functions")
    required_runtime_literals = _extract_list_from_prompt(prompt, "required_runtime_literals")
    forbidden_runtime_literals = _extract_list_from_prompt(prompt, "forbidden_runtime_literals")
    forbidden_raw_runtime_fields = _extract_list_from_prompt(prompt, "forbidden_raw_runtime_fields")

    screens = [
        {
            "screen_id": screen_id,
            "purpose": f"{screen_id} runtime screen",
            "interaction_type": "coaching_feedback" if "FOLLOW_UP" in screen_id else "feedback" if "RESULT" in screen_id else "free_text_input" if screen_id == "SCREEN_INPUT" else "multiple_choice" if "MULTIPLE_CHOICE" in screen_id else "display_content",
            "required_ui_elements": [screen_id],
        }
        for screen_id in required_screen_constants
    ]
    transitions = []
    previous_screen = required_screen_constants[0] if required_screen_constants else "SCREEN_START"
    for assignment in required_transition_assignments:
        target_match = re.search(r"=\s*(SCREEN_[A-Z_]+)", assignment)
        to_screen = target_match.group(1) if target_match else previous_screen
        transitions.append(
            {
                "from_screen": previous_screen,
                "to_screen": to_screen,
                "trigger": "state transition",
                "state_assignment": assignment,
            }
        )
        previous_screen = to_screen

    error_path = None
    if "SCREEN_ERROR" in required_screen_constants:
        error_path = {
            "target_screen": "SCREEN_ERROR",
            "trigger": "invalid input or exception",
            "state_assignment": "st.session_state.current_screen = SCREEN_ERROR",
            "notes": "explicit error path",
        }

    result_target = (
        "SCREEN_RESULT"
        if "SCREEN_RESULT" in required_screen_constants
        else "SCREEN_SESSION_RESULT"
        if "SCREEN_SESSION_RESULT" in required_screen_constants
        else next((screen for screen in required_screen_constants if "RESULT" in screen), "")
    )
    result_path = None
    if result_target:
        result_path = {
            "target_screen": result_target,
            "trigger": "submit completed",
            "state_assignment": next(
                (
                    assignment
                    for assignment in required_transition_assignments
                    if result_target in assignment
                ),
                "",
            ),
            "notes": "primary result path",
        }

    return {
        "interaction_mode": interaction_mode,
        "content_runtime_source": content_runtime_source,
        "content_loading_order": "outputs_first",
        "screens": screens,
        "transitions": transitions,
        "required_functions": required_functions,
        "required_runtime_literals": required_runtime_literals,
        "forbidden_runtime_literals": forbidden_runtime_literals,
        "forbidden_raw_runtime_fields": forbidden_raw_runtime_fields,
        "data_bindings": {
            "runtime_collection": content_runtime_source,
            "forbidden_runtime_literals": forbidden_runtime_literals,
            "forbidden_raw_runtime_fields": forbidden_raw_runtime_fields,
        },
        "error_path": error_path,
        "result_path": result_path,
        "generation_notes": ["fake deterministic AppFlowPlan"],
    }


def _build_llm_generated_streamlit_source(content_filename: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

# LLM_GENERATED_APP_MARKER
CONTENT_FILENAME = "{content_filename}"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_SESSION_RESULT = "S5"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_contents() -> dict[str, Any]:
    content_path = resolve_content_path()
    if content_path is None:
        return {{}}
    return json.loads(content_path.read_text(encoding="utf-8"))


def ensure_state() -> None:
    st.session_state.setdefault("current_screen", SCREEN_START)
    st.session_state.setdefault("session_quests", [])
    st.session_state.setdefault("current_quest_index", 0)
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_submission", "")


def normalize_quest(item: dict[str, Any]) -> dict[str, Any]:
    options = list(item.get("choices", []))
    correct_option_text = item.get("correct_choice")
    correct_option_index = options.index(correct_option_text) if correct_option_text in options else None
    return {{
        "quest_id": item.get("item_id", "item-1"),
        "quest_type": item.get("quiz_type", "multiple_choice"),
        "difficulty": item.get("difficulty", "intro"),
        "title": item.get("title", "LLM Generated Item"),
        "question": item.get("question", ""),
        "original_question": item.get("original_question", item.get("question", "")),
        "topic_context": item.get("topic_context", "학습 맥락"),
        "options": options,
        "correct_option_text": correct_option_text,
        "correct_option_index": correct_option_index,
        "explanation": item.get("explanation", ""),
        "learning_point": item.get("learning_point", ""),
    }}


def build_session_quests(data: dict[str, Any]) -> list[dict[str, Any]]:
    items = [normalize_quest(item) for item in data.get("items", [])[:3]]
    return items


def screen_for_quest(quest: dict[str, Any], *, feedback: bool = False) -> str:
    if quest.get("quest_type") == "multiple_choice":
        return SCREEN_MULTIPLE_CHOICE_RESULT if feedback else SCREEN_MULTIPLE_CHOICE
    return SCREEN_IMPROVEMENT_RESULT if feedback else SCREEN_IMPROVEMENT


def api_session_start() -> dict[str, Any]:
    data = load_contents()
    quests = build_session_quests(data)
    st.session_state.session_quests = quests
    st.session_state.current_quest_index = 0
    st.session_state.current_screen = screen_for_quest(quests[0]) if quests else SCREEN_START
    return {{"session_id": "fake-session", "quests": quests}}


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.session_state.last_submission = user_response
    st.session_state.current_screen = screen_for_quest(quest, feedback=True)
    return {{
        "answer_id": "fake-answer",
        "evaluation": {{"evaluation_type": "correctness", "feedback": "테스트 응답입니다."}},
        "earned_score": 0,
        "is_session_complete": False,
        "user_response": user_response,
    }}


def api_session_result() -> dict[str, Any]:
    return {{"session_score": 0, "current_grade": "bronze"}}


def render_multiple_choice_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.write(quest.get("question", ""))
    choice_key = f"choice_{{quest['quest_id']}}"
    st.radio("선택지를 고르세요.", quest.get("options", []), index=None, key=choice_key)
    if st.button("제출", key="submit_mc"):
        selected = st.session_state.get(choice_key)
        if selected:
            api_quest_submit(selected)
            st.rerun()


def render_multiple_choice_result() -> None:
    st.write("객관식 결과")
    if st.button("다음", key="next_mc"):
        st.session_state.current_screen = SCREEN_IMPROVEMENT
        st.rerun()


def render_improvement_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.write(quest.get("question", ""))
    text_key = f"text_{{quest['quest_id']}}"
    user_text = st.text_area("질문 다시 쓰기", key=text_key)
    if st.button("제출", key="submit_improvement") and user_text.strip():
        api_quest_submit(user_text.strip())
        st.rerun()


def render_improvement_result() -> None:
    st.write("개선형 결과")
    if st.button("결과 보기", key="view_session_result"):
        st.session_state.current_screen = SCREEN_SESSION_RESULT
        st.rerun()


def render_session_result() -> None:
    st.write("세션 결과")


def main() -> None:
    st.set_page_config(page_title="LLM Generated MVP", layout="wide")
    ensure_state()
    st.title("LLM Generated MVP")
    data = load_contents()
    if not data:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
        return
    if not st.session_state.session_quests:
        api_session_start()
    if st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE:
        render_multiple_choice_screen()
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE_RESULT:
        render_multiple_choice_result()
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT:
        render_improvement_screen()
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT_RESULT:
        render_improvement_result()
    elif st.session_state.current_screen == SCREEN_SESSION_RESULT:
        render_session_result()
    else:
        st.write(f"총 {{len(data.get('items', []))}}개 콘텐츠를 읽었습니다.")


main()
'''


def _build_coaching_llm_generated_streamlit_source(content_filename: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

# LLM_GENERATED_APP_MARKER
CONTENT_FILENAME = "{content_filename}"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_START = "S0"
SCREEN_INPUT = "S1"
SCREEN_FOLLOW_UP = "S2"
SCREEN_RESULT = "S3"
SCREEN_ERROR = "S4"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_contents() -> dict[str, Any]:
    content_path = resolve_content_path()
    if content_path is None:
        return {{}}
    return json.loads(content_path.read_text(encoding="utf-8"))


def ensure_state() -> None:
    st.session_state.setdefault("current_screen", SCREEN_START)
    st.session_state.setdefault("interaction_units", [])
    st.session_state.setdefault("turn_count", 0)
    st.session_state.setdefault("current_feedback", "")
    st.session_state.setdefault("last_input", "")
    st.session_state.setdefault("improved_question", "")


def detect_missing_dimension(user_input: str) -> str:
    lowered = user_input.lower()
    if len(lowered.strip()) < 10:
        return "need_specificity"
    if not any(marker in lowered for marker in ["수학", "과학", "사회", "발표", "숙제", "수행평가"]):
        return "need_context"
    if not any(marker in lowered for marker in ["이유", "방법", "설명", "예시", "도와"]):
        return "need_purpose"
    return "completed"


def build_follow_up_question(mode: str) -> str:
    prompts = {{
        "need_specificity": "무엇이 궁금한지 조금 더 구체적으로 적어볼래요?",
        "need_context": "어떤 과목이나 상황에서 필요한 질문인지 알려줄래요?",
        "need_purpose": "이 질문으로 무엇을 알고 싶은지 말해줄래요?",
    }}
    return prompts.get(mode, "한 번 더 자세히 적어볼래요?")


def build_improved_question(user_input: str, mode: str) -> str:
    suffix = {{
        "need_specificity": "핵심 개념과 범위를 포함해 설명해줘.",
        "need_context": "과목과 상황을 반영해서 설명해줘.",
        "need_purpose": "내가 왜 이 내용을 묻는지 고려해서 설명해줘.",
        "completed": "내 상황에 맞는 답을 예시와 함께 설명해줘.",
    }}.get(mode, "조금 더 자세히 설명해줘.")
    return f"{{user_input.strip()}} {{suffix}}".strip()


def api_session_start() -> dict[str, Any]:
    data = load_contents()
    st.session_state.interaction_units = data.get("interaction_units", [])
    st.session_state.turn_count = 0
    st.session_state.current_feedback = ""
    st.session_state.last_input = ""
    st.session_state.improved_question = ""
    st.session_state.current_screen = SCREEN_INPUT
    return {{"session_id": "coaching-session", "interaction_units": st.session_state.interaction_units}}


def api_chat_submit(user_response: str) -> dict[str, Any]:
    if not user_response.strip():
        st.session_state.current_feedback = "질문을 입력해주세요."
        st.session_state.current_screen = SCREEN_ERROR
        return {{"mode": "error", "next_action": "ask_more"}}

    st.session_state.last_input = user_response.strip()
    mode = detect_missing_dimension(st.session_state.last_input)
    st.session_state.turn_count += 1
    if st.session_state.turn_count >= 2:
        mode = "completed"

    st.session_state.improved_question = build_improved_question(st.session_state.last_input, mode)
    if mode == "completed":
        st.session_state.current_feedback = "질문이 충분히 구체적이어서 바로 개선 결과를 보여줄게요."
        st.session_state.current_screen = SCREEN_RESULT
        return {{"mode": mode, "next_action": "show_result"}}

    st.session_state.current_feedback = build_follow_up_question(mode)
    st.session_state.current_screen = SCREEN_FOLLOW_UP
    return {{"mode": mode, "next_action": "ask_more"}}


def api_session_result() -> dict[str, Any]:
    return {{
        "original_question": st.session_state.last_input,
        "improved_question": st.session_state.improved_question,
        "turn_count": st.session_state.turn_count,
    }}


def render_input_screen() -> None:
    user_text = st.text_area("질문 입력", key="chat_input")
    if st.button("진단하기", key="submit_input") and user_text.strip():
        api_chat_submit(user_text)
        st.rerun()


def render_follow_up_screen() -> None:
    st.write(st.session_state.current_feedback)
    follow_up = st.text_area("보완한 질문", key="follow_up_input")
    if st.button("다시 진단하기", key="submit_follow_up") and follow_up.strip():
        api_chat_submit(follow_up)
        st.rerun()


def render_result_screen() -> None:
    result = api_session_result()
    st.write(result.get("improved_question", ""))


def render_error_screen() -> None:
    st.warning(st.session_state.current_feedback)
    if st.button("입력 화면으로 돌아가기", key="back_to_input"):
        st.session_state.current_screen = SCREEN_INPUT
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="LLM Generated MVP", layout="wide")
    ensure_state()
    st.title("LLM Generated MVP")
    data = load_contents()
    if not data:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
        return
    if not st.session_state.interaction_units:
        api_session_start()
    if st.session_state.current_screen == SCREEN_START:
        st.session_state.current_screen = SCREEN_INPUT
        st.rerun()
    elif st.session_state.current_screen == SCREEN_INPUT:
        render_input_screen()
    elif st.session_state.current_screen == SCREEN_FOLLOW_UP:
        render_follow_up_screen()
    elif st.session_state.current_screen == SCREEN_RESULT:
        render_result_screen()
    elif st.session_state.current_screen == SCREEN_ERROR:
        render_error_screen()
    else:
        st.write("알 수 없는 화면입니다.")


main()
'''


def _build_quest_v2_llm_generated_streamlit_source(content_filename: str) -> str:
    return f'''from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

# LLM_GENERATED_APP_MARKER
CONTENT_FILENAME = "{content_filename}"
APP_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_BATTLE = "S5"
SCREEN_BATTLE_RESULT = "S6"
SCREEN_BATTLE_COMPLETED = "S7"
SCREEN_SESSION_RESULT = "S8"


def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None


def load_contents() -> dict[str, Any]:
    content_path = resolve_content_path()
    if content_path is None:
        return {{}}
    return json.loads(content_path.read_text(encoding="utf-8"))


def ensure_state() -> None:
    st.session_state.setdefault("current_screen", SCREEN_START)
    st.session_state.setdefault("session_quests", [])
    st.session_state.setdefault("current_quest_index", 0)
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_submission", "")
    st.session_state.setdefault("battle_history", [])
    st.session_state.setdefault("session_result", None)


def normalize_quest(item: dict[str, Any]) -> dict[str, Any]:
    options = list(item.get("choices", []))
    correct_option_text = item.get("correct_choice")
    correct_option_index = options.index(correct_option_text) if correct_option_text in options else None
    return {{
        "quest_id": item.get("item_id", "quest-1"),
        "quest_type": item.get("quiz_type", "multiple_choice"),
        "difficulty": item.get("difficulty", "main"),
        "title": item.get("title", ""),
        "question": item.get("question", ""),
        "original_question": item.get("original_question", item.get("question", "")),
        "topic_context": item.get("topic_context", ""),
        "options": options,
        "correct_option_text": correct_option_text,
        "correct_option_index": correct_option_index,
        "explanation": item.get("explanation", ""),
        "learning_point": item.get("learning_point", ""),
        "stage_level": item.get("stage_level", "round"),
        "ai_question": item.get("ai_question", ""),
        "situation": item.get("situation", ""),
    }}


def build_session_quests(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [normalize_quest(item) for item in data.get("items", [])]


def screen_for_quest(quest: dict[str, Any]) -> str:
    if quest.get("quest_type") == "multiple_choice":
        return SCREEN_MULTIPLE_CHOICE
    if quest.get("quest_type") == "battle":
        return SCREEN_BATTLE
    return SCREEN_IMPROVEMENT


def api_session_start() -> dict[str, Any]:
    data = load_contents()
    quests = build_session_quests(data)
    st.session_state.session_quests = quests
    st.session_state.current_quest_index = 0
    st.session_state.current_screen = screen_for_quest(quests[0]) if quests else SCREEN_START
    st.session_state.last_result = None
    st.session_state.battle_history = []
    st.session_state.session_result = None
    return {{"session_id": "quest-v2-fake", "quests": quests}}


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.session_state.last_submission = user_response
    if quest.get("quest_type") == "multiple_choice":
        st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
    elif quest.get("quest_type") == "battle":
        st.session_state.current_screen = SCREEN_BATTLE_RESULT
    else:
        st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
    result = {{
        "answer_id": f"answer-{{quest['quest_id']}}",
        "evaluation": {{"evaluation_type": "heuristic", "feedback": "테스트 응답입니다."}},
        "earned_score": 10,
        "is_session_complete": False,
        "user_response": user_response,
    }}
    st.session_state.last_result = result
    if quest.get("quest_type") == "battle":
        st.session_state.battle_history.append(result)
    return result


def api_session_result() -> dict[str, Any]:
    result = {{
        "session_score": len(st.session_state.session_quests) * 10,
        "current_grade": "silver",
    }}
    st.session_state.session_result = result
    return result


def advance_after_feedback() -> None:
    current_index = st.session_state.current_quest_index
    quests = st.session_state.session_quests
    current_quest = quests[current_index]
    if current_quest.get("quest_type") == "battle":
        st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
        return
    next_index = current_index + 1
    if next_index >= len(quests):
        api_session_result()
        st.session_state.current_screen = SCREEN_SESSION_RESULT
        return
    st.session_state.current_quest_index = next_index
    next_quest = quests[next_index]
    if next_quest.get("quest_type") == "battle":
        st.session_state.current_screen = SCREEN_BATTLE
    elif next_quest.get("quest_type") == "multiple_choice":
        st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
    else:
        st.session_state.current_screen = SCREEN_IMPROVEMENT


def complete_battle_and_session() -> None:
    api_session_result()
    st.session_state.current_screen = SCREEN_SESSION_RESULT


def render_multiple_choice_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    choice_key = f"choice_{{quest['quest_id']}}"
    st.write(quest.get("question", ""))
    st.radio("선택지를 고르세요.", quest.get("options", []), index=None, key=choice_key)
    if st.button("제출", key="submit_mc"):
        selected = st.session_state.get(choice_key)
        if selected:
            api_quest_submit(selected)
            st.rerun()


def render_multiple_choice_result() -> None:
    st.write("객관식 결과")
    if st.button("다음", key="next_mc"):
        advance_after_feedback()
        st.rerun()


def render_improvement_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    text_key = f"text_{{quest['quest_id']}}"
    st.write(quest.get("question", ""))
    user_text = st.text_area("답변 입력", key=text_key)
    if st.button("제출", key="submit_improvement") and user_text.strip():
        api_quest_submit(user_text.strip())
        st.rerun()


def render_improvement_result() -> None:
    st.write("개선형 결과")
    if st.button("다음", key="next_improvement"):
        advance_after_feedback()
        st.rerun()


def render_battle_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    text_key = f"battle_{{quest['quest_id']}}"
    st.write(quest.get("question", ""))
    user_text = st.text_area("배틀 답변 입력", key=text_key)
    if st.button("배틀 제출", key="submit_battle") and user_text.strip():
        api_quest_submit(user_text.strip())
        st.rerun()


def render_battle_result() -> None:
    st.write("배틀 라운드 결과")
    if st.button("배틀 완료", key="complete_battle"):
        st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
        st.rerun()


def render_battle_completed() -> None:
    st.write("배틀 종료")
    if st.button("세션 결과 보기", key="battle_to_session"):
        complete_battle_and_session()
        st.rerun()


def render_session_result() -> None:
    result = st.session_state.session_result or api_session_result()
    st.write(result.get("current_grade", "silver"))


def main() -> None:
    st.set_page_config(page_title="LLM Generated MVP", layout="wide")
    ensure_state()
    st.title("LLM Generated MVP")
    data = load_contents()
    if not data:
        st.warning("콘텐츠 파일을 찾지 못했습니다.")
        return
    if not st.session_state.session_quests:
        api_session_start()
    if st.session_state.current_screen == SCREEN_START:
        if st.button("세션 시작", key="start_session"):
            first_quest = st.session_state.session_quests[0]
            st.session_state.current_screen = screen_for_quest(first_quest)
            st.rerun()
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE:
        render_multiple_choice_screen()
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE_RESULT:
        render_multiple_choice_result()
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT:
        render_improvement_screen()
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT_RESULT:
        render_improvement_result()
    elif st.session_state.current_screen == SCREEN_BATTLE:
        render_battle_screen()
    elif st.session_state.current_screen == SCREEN_BATTLE_RESULT:
        render_battle_result()
    elif st.session_state.current_screen == SCREEN_BATTLE_COMPLETED:
        render_battle_completed()
    elif st.session_state.current_screen == SCREEN_SESSION_RESULT:
        render_session_result()
    else:
        st.write("알 수 없는 화면입니다.")


main()
'''


def _prompt_requires_v2_builder_contract(prompt: str) -> bool:
    markers = [
        "requires_battle: true",
        "/api/battle/submit",
        '"quest_sequence": ["multiple_choice", "situation_card", "question_improvement", "situation_card", "battle"]',
        "multiple_choice → situation_card → question_improvement → situation_card → battle",
    ]
    return any(marker in prompt for marker in markers)


def _prompt_requires_coaching_builder_contract(prompt: str) -> bool:
    return re.search(r'interaction_mode:\s*"?(coaching)"?', prompt, re.IGNORECASE) is not None
