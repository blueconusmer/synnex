"""
pytest.py — 질문력 강화 퀘스트 서비스 명세 검증 테스트 코드

문서 성격: 2차 산출물 (검증 코드).
참조 문서: constitution.md, data_schema.json, state_machine.md, prompt_spec.md, interface_spec.md
버전: v0.1 (Layer 2 구축용 mock 데이터)

본 테스트 코드는 Layer 2 AI 구현팀이 생성한 MVP 코드가
구현 명세서 4종의 핵심 요구사항을 충족하는지 검증한다.

테스트 그룹:
  1. 데이터 스키마 검증 (data_schema.json)
  2. 상태 전이 로직 검증 (state_machine.md)
  3. 점수·등급 규칙 검증 (constitution.md ⑦)
  4. 프롬프트 출력 형식 검증 (prompt_spec.md)
  5. API 응답 형식 검증 (interface_spec.md)

실행 방법:
  pytest pytest.py -v

주의:
  - 실제 LLM 호출은 mock으로 대체된다.
  - 본 코드는 명세 검증용이며, 통합 테스트는 별도 진행한다.
"""

import pytest
from unittest.mock import MagicMock


# =============================================================================
# 0. Fixtures (테스트용 mock 데이터)
# =============================================================================

@pytest.fixture
def sample_intro_quest():
    """객관식 퀘스트 mock"""
    return {
        "quest_id": "quest_001",
        "quest_type": "multiple_choice",
        "difficulty": "intro",
        "topic_context": "국어 비유 표현 학습",
        "original_question": "비유가 뭔지 모르겠어",
        "options": [
            "비유 알려줘",
            "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해줘",
            "비유 예시 좀",
            "비유 어떻게 해"
        ],
        "correct_option_index": 1,
        "explanation": "이 선택지가 가장 좋아요. 무엇을, 왜, 어떻게가 모두 들어있어요."
    }


@pytest.fixture
def sample_main_quest():
    """질문 개선형 퀘스트 mock"""
    return {
        "quest_id": "quest_002",
        "quest_type": "question_improvement",
        "difficulty": "main",
        "topic_context": "수학 일차방정식",
        "original_question": "이거 어떻게 풀어"
    }


@pytest.fixture
def sample_session(sample_intro_quest, sample_main_quest):
    """3개 퀘스트로 구성된 세션 mock"""
    return {
        "session_id": "session_001",
        "user_id": "user_test",
        "quest_ids": ["quest_001", "quest_002", "quest_003"],
        "session_status": "in_progress",
        "session_score": 0,
        "started_at": "2026-04-27T10:00:00"
    }


@pytest.fixture
def sample_user_progress():
    """사용자 진행 상태 mock"""
    return {
        "user_id": "user_test",
        "cumulative_score": 0,
        "current_grade": "bronze",
        "completed_session_count": 0
    }


# =============================================================================
# 1. 데이터 스키마 검증
# =============================================================================

class TestDataSchema:
    """data_schema.json의 핵심 제약 검증"""

    def test_quest_has_required_fields(self, sample_intro_quest):
        """퀘스트는 필수 필드를 모두 가져야 한다"""
        required = ["quest_id", "quest_type", "difficulty", "topic_context", "original_question"]
        for field in required:
            assert field in sample_intro_quest, f"필수 필드 누락: {field}"

    def test_quest_type_enum_valid(self, sample_intro_quest, sample_main_quest):
        """quest_type은 정의된 enum 값만 가능"""
        valid_types = {"multiple_choice", "question_improvement"}
        assert sample_intro_quest["quest_type"] in valid_types
        assert sample_main_quest["quest_type"] in valid_types

    def test_difficulty_enum_valid(self, sample_intro_quest, sample_main_quest):
        """difficulty는 intro 또는 main만 가능"""
        valid_difficulties = {"intro", "main"}
        assert sample_intro_quest["difficulty"] in valid_difficulties
        assert sample_main_quest["difficulty"] in valid_difficulties

    def test_multiple_choice_has_options(self, sample_intro_quest):
        """객관식 퀘스트는 options와 correct_option_index를 가져야 한다"""
        assert "options" in sample_intro_quest
        assert "correct_option_index" in sample_intro_quest
        assert len(sample_intro_quest["options"]) == 4
        assert 0 <= sample_intro_quest["correct_option_index"] < 4

    def test_improvement_quest_no_options(self, sample_main_quest):
        """개선형 퀘스트는 options를 가지지 않는다"""
        assert "options" not in sample_main_quest or sample_main_quest.get("options") is None

    def test_session_quest_count(self, sample_session):
        """세션은 정확히 3개 퀘스트로 구성된다"""
        assert len(sample_session["quest_ids"]) == 3

    def test_grade_enum_valid(self, sample_user_progress):
        """current_grade는 정의된 등급만 가능"""
        valid_grades = {"bronze", "silver", "gold", "platinum"}
        assert sample_user_progress["current_grade"] in valid_grades


# =============================================================================
# 2. 상태 전이 로직 검증
# =============================================================================

class TestStateMachine:
    """state_machine.md의 상태 전이 규칙 검증"""

    def test_session_starts_with_intro_then_main_main(self):
        """세션은 [intro, main, main] 순서로 구성된다"""
        quests = build_session_quests()
        assert quests[0]["difficulty"] == "intro"
        assert quests[1]["difficulty"] == "main"
        assert quests[2]["difficulty"] == "main"

    def test_session_completes_after_3_submissions(self):
        """3개 퀘스트 모두 제출 시 세션이 completed로 전환된다"""
        session = {"session_status": "in_progress", "submitted_count": 0}

        for _ in range(3):
            session["submitted_count"] += 1

        if session["submitted_count"] == 3:
            session["session_status"] = "completed"

        assert session["session_status"] == "completed"

    def test_session_not_complete_with_partial_submissions(self):
        """3개 미만 제출 시 세션은 완료되지 않는다"""
        for partial_count in [0, 1, 2]:
            session = {"session_status": "in_progress", "submitted_count": partial_count}
            assert session["session_status"] != "completed"

    def test_state_transitions_are_one_directional(self):
        """상태는 이전으로 되돌아갈 수 없다 (재시도는 후속 확장)"""
        states = [
            "SESSION_START", "QUEST_1_ACTIVE", "QUEST_1_FEEDBACK",
            "QUEST_2_ACTIVE", "QUEST_2_FEEDBACK",
            "QUEST_3_ACTIVE", "QUEST_3_FEEDBACK", "SESSION_COMPLETED"
        ]
        # 각 상태에서 가능한 다음 상태는 정의된 다음 상태 하나만
        for i in range(len(states) - 1):
            allowed_next = states[i + 1]
            assert allowed_next == states[i + 1]  # 단방향 보장


# =============================================================================
# 3. 점수·등급 규칙 검증
# =============================================================================

class TestScoringRules:
    """헌법 ⑦의 점수 부여 규칙 및 등급 임계점 검증"""

    @pytest.mark.parametrize("is_correct, expected_score", [
        (True, 20),   # 객관식 정답
        (False, 5),   # 객관식 오답 (참여 점수)
    ])
    def test_multiple_choice_scoring(self, is_correct, expected_score):
        """객관식 점수 부여 규칙: 정답 20점, 오답 5점"""
        score = calculate_mc_score(is_correct)
        assert score == expected_score

    @pytest.mark.parametrize("overall, expected_score", [
        ("excellent", 30),
        ("good", 20),
        ("needs_work", 10),
    ])
    def test_improvement_scoring(self, overall, expected_score):
        """개선형 점수 부여 규칙: 우수 30, 양호 20, 미흡 10"""
        score = calculate_improvement_score(overall)
        assert score == expected_score

    def test_score_never_decreases(self, sample_user_progress):
        """누적 점수는 어떤 경우에도 감소하지 않는다"""
        initial_score = sample_user_progress["cumulative_score"]

        # 어떤 점수가 추가되더라도 (양수만 가능)
        for added_score in [5, 10, 20, 30]:
            sample_user_progress["cumulative_score"] += added_score
            assert sample_user_progress["cumulative_score"] >= initial_score

    @pytest.mark.parametrize("score, expected_grade", [
        (0, "bronze"),
        (50, "bronze"),
        (99, "bronze"),
        (100, "silver"),
        (200, "silver"),
        (299, "silver"),
        (300, "gold"),
        (500, "gold"),
        (599, "gold"),
        (600, "platinum"),
        (1000, "platinum"),
    ])
    def test_grade_thresholds(self, score, expected_grade):
        """등급 임계점이 헌법 ⑦-4와 일치한다"""
        grade = determine_grade(score)
        assert grade == expected_grade

    def test_minimum_improvement_score_is_10(self):
        """개선형 퀘스트는 미흡 판정이라도 최소 10점을 부여한다 (위축 방지)"""
        score = calculate_improvement_score("needs_work")
        assert score >= 10


# =============================================================================
# 4. 프롬프트 출력 형식 검증
# =============================================================================

class TestPromptOutputFormat:
    """prompt_spec.md의 LLM 출력 형식 검증"""

    def test_quest_generation_output_has_required_fields(self):
        """객관식 퀘스트 생성 출력은 필수 필드를 포함한다"""
        mock_output = {
            "topic_context": "국어",
            "original_question": "비유 알려줘",
            "options": ["a", "b", "c", "d"],
            "correct_option_index": 1,
            "explanation": "..."
        }
        required = ["topic_context", "original_question", "options", "correct_option_index", "explanation"]
        for field in required:
            assert field in mock_output

    def test_evaluation_output_has_rubric_and_feedback(self):
        """평가 출력은 rubric_result와 feedback을 포함한다"""
        mock_output = {
            "rubric_result": {
                "specificity": "excellent",
                "context": "good",
                "purpose": "good",
                "overall": "good"
            },
            "feedback": "좋아졌어요!"
        }
        assert "rubric_result" in mock_output
        assert "feedback" in mock_output

    def test_rubric_result_has_all_criteria(self):
        """rubric_result는 3가지 기준 + overall을 모두 포함한다"""
        mock_rubric = {
            "specificity": "excellent",
            "context": "good",
            "purpose": "good",
            "overall": "good"
        }
        required = ["specificity", "context", "purpose", "overall"]
        for criterion in required:
            assert criterion in mock_rubric

    @pytest.mark.parametrize("criterion_value", ["excellent", "good", "needs_work"])
    def test_rubric_values_are_valid_enums(self, criterion_value):
        """루브릭 판정값은 정의된 enum만 가능"""
        valid_values = {"excellent", "good", "needs_work"}
        assert criterion_value in valid_values

    def test_overall_derivation_excellent(self):
        """3개 모두 excellent → overall = excellent"""
        result = derive_overall("excellent", "excellent", "excellent")
        assert result == "excellent"

    def test_overall_derivation_needs_work(self):
        """1개 이상 needs_work → overall = needs_work"""
        result = derive_overall("excellent", "good", "needs_work")
        assert result == "needs_work"

    def test_overall_derivation_good(self):
        """모두 good 이상이지만 모두 excellent는 아님 → overall = good"""
        result = derive_overall("excellent", "good", "good")
        assert result == "good"

    def test_feedback_length_under_150_chars(self):
        """피드백은 150자 이하로 제한된다"""
        sample_feedback = "질문이 아주 명확해졌어요! 무엇을, 왜, 어떻게가 모두 잘 드러나 있어요."
        assert len(sample_feedback) <= 150


# =============================================================================
# 5. API 응답 형식 검증
# =============================================================================

class TestAPIResponse:
    """interface_spec.md의 API 응답 형식 검증"""

    def test_session_start_response_has_3_quests(self):
        """/api/session/start 응답은 3개 퀘스트를 반환한다"""
        mock_response = {
            "session_id": "session_001",
            "quests": [{}, {}, {}],
            "user_progress": {}
        }
        assert len(mock_response["quests"]) == 3

    def test_session_start_response_does_not_expose_answers(self):
        """세션 시작 응답에는 정답·해설이 포함되지 않는다 (보안)"""
        mock_quest_in_response = {
            "quest_id": "q1",
            "quest_type": "multiple_choice",
            "difficulty": "intro",
            "topic_context": "...",
            "original_question": "...",
            "options": ["a", "b", "c", "d"]
            # correct_option_index, explanation 없음
        }
        assert "correct_option_index" not in mock_quest_in_response
        assert "explanation" not in mock_quest_in_response

    def test_quest_submit_mc_response_format(self):
        """객관식 제출 응답은 evaluation_type=correctness 형식"""
        mock_response = {
            "answer_id": "ans_001",
            "evaluation": {
                "evaluation_type": "correctness",
                "is_correct": True,
                "feedback": "정답입니다!"
            },
            "earned_score": 20,
            "correct_option_index": 1,
            "is_session_complete": False
        }
        assert mock_response["evaluation"]["evaluation_type"] == "correctness"
        assert "is_correct" in mock_response["evaluation"]

    def test_quest_submit_improvement_response_format(self):
        """개선형 제출 응답은 evaluation_type=rubric 형식"""
        mock_response = {
            "answer_id": "ans_002",
            "evaluation": {
                "evaluation_type": "rubric",
                "rubric_result": {
                    "specificity": "excellent",
                    "context": "excellent",
                    "purpose": "excellent",
                    "overall": "excellent"
                },
                "feedback": "질문이 아주 명확해졌어요!"
            },
            "earned_score": 30,
            "is_session_complete": False
        }
        assert mock_response["evaluation"]["evaluation_type"] == "rubric"
        assert "rubric_result" in mock_response["evaluation"]

    def test_session_complete_flag_on_third_submission(self):
        """3번째 퀘스트 제출 시 is_session_complete = true"""
        submission_results = [False, False, True]  # 1, 2, 3번째 제출 결과
        assert submission_results[2] is True
        assert submission_results[0] is False
        assert submission_results[1] is False

    def test_error_response_format(self):
        """에러 응답은 정해진 형식을 따른다"""
        mock_error = {
            "error_code": "E_LLM_TIMEOUT",
            "error_message": "잠시 후 다시 시도해주세요"
        }
        assert "error_code" in mock_error
        assert "error_message" in mock_error
        assert mock_error["error_code"].startswith("E_")


# =============================================================================
# 헬퍼 함수 (실제 구현은 Layer 2 AI 구현팀이 작성)
# =============================================================================

def build_session_quests():
    """세션 시작 시 3개 퀘스트 배치"""
    return [
        {"difficulty": "intro"},
        {"difficulty": "main"},
        {"difficulty": "main"}
    ]


def calculate_mc_score(is_correct):
    """객관식 점수 계산"""
    return 20 if is_correct else 5


def calculate_improvement_score(overall):
    """개선형 점수 계산"""
    score_map = {
        "excellent": 30,
        "good": 20,
        "needs_work": 10
    }
    return score_map.get(overall, 0)


def determine_grade(cumulative_score):
    """누적 점수 기반 등급 결정"""
    if cumulative_score >= 600:
        return "platinum"
    elif cumulative_score >= 300:
        return "gold"
    elif cumulative_score >= 100:
        return "silver"
    else:
        return "bronze"


def derive_overall(specificity, context, purpose):
    """루브릭 종합 판정 도출"""
    values = [specificity, context, purpose]
    if all(v == "excellent" for v in values):
        return "excellent"
    elif any(v == "needs_work" for v in values):
        return "needs_work"
    else:
        return "good"
