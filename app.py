from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
SERVICE_NAME = "질문력 강화 퀘스트"
CONTENT_FILENAME = "question_quest_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

SCREENS = ["S0", "S1", "S2", "S3", "S4", "S5"]
SCREEN_START = "S0"
SCREEN_MULTIPLE_CHOICE = "S1"
SCREEN_MULTIPLE_CHOICE_RESULT = "S2"
SCREEN_IMPROVEMENT = "S3"
SCREEN_IMPROVEMENT_RESULT = "S4"
SCREEN_SESSION_RESULT = "S5"

API_ENDPOINTS = [
    "/api/session/start",
    "/api/quest/submit",
    "/api/session/result",
]

SCORE_RULES = {
    "answer_score_rules": {
        "multiple_choice_correct": 20,
        "multiple_choice_incorrect": 5,
        "improvement_excellent": 30,
        "improvement_good": 20,
        "improvement_needs_work": 10,
    },
    "service_grades": {
        "브론즈": [0, 99],
        "실버": [100, 299],
        "골드": [300, 599],
        "플래티넘": [600, None],
    },
}
GRADE_LEVELS = ["브론즈", "실버", "골드", "플래티넘"]
GRADE_THRESHOLDS = {
    "브론즈": {"min_score": 0, "max_score": 99},
    "실버": {"min_score": 100, "max_score": 299},
    "골드": {"min_score": 300, "max_score": 599},
    "플래티넘": {"min_score": 600, "max_score": None},
}

IMPROVEMENT_MIN_LENGTH = 10
IMPROVEMENT_MAX_LENGTH = 300
SPECIFICITY_MARKERS = [
    "예시",
    "단계",
    "문장",
    "문단",
    "그래프",
    "수식",
    "비유",
    "원인",
    "방법",
    "비교",
    "3개",
    "한 문장",
    "단계별",
    "구체",
    "어떤 문제",
    "왜",
    "어떻게",
]
CONTEXT_MARKERS = [
    "국어",
    "수학",
    "과학",
    "사회",
    "역사",
    "영어",
    "숙제",
    "발표",
    "시험",
    "수행평가",
    "수업",
    "실험",
    "독후감",
    "글쓰기",
    "프로젝트",
    "과제",
]
PURPOSE_MARKERS = [
    "설명",
    "예시",
    "풀이",
    "방법",
    "이유",
    "비교",
    "알려줘",
    "보여줘",
    "정리",
    "도와줘",
    "알고 싶",
    "말해줘",
    "어떻게",
    "왜",
]


def resolve_content_path() -> Path | None:
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None


@st.cache_data(show_spinner=False)
def load_quest_contents() -> dict[str, Any]:
    content_path = resolve_content_path()
    if content_path is None:
        return {}
    return json.loads(content_path.read_text(encoding="utf-8"))


def ensure_state() -> None:
    defaults = {
        "current_screen": SCREEN_START,
        "session_id": "",
        "session_quests": [],
        "current_quest_index": 0,
        "session_score": 0,
        "cumulative_score": 0,
        "current_grade": GRADE_LEVELS[0],
        "completed_session_count": 0,
        "last_result": None,
        "last_submission": "",
        "session_finalized": False,
        "grade_up_event": None,
        "previous_grade": GRADE_LEVELS[0],
        "last_api_response": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_session_progress() -> None:
    st.session_state.session_id = ""
    st.session_state.session_quests = []
    st.session_state.current_quest_index = 0
    st.session_state.session_score = 0
    st.session_state.last_result = None
    st.session_state.last_submission = ""
    st.session_state.session_finalized = False
    st.session_state.grade_up_event = None
    st.session_state.last_api_response = None
    st.session_state.current_screen = SCREEN_START


def truncate_feedback(text: str, limit: int = 150) -> str:
    compact = " ".join(text.split())
    return compact[:limit].rstrip()


def contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def get_grade_rank(grade: str) -> int:
    try:
        return GRADE_LEVELS.index(grade)
    except ValueError:
        return -1


def determine_grade(score: int) -> str:
    for grade in GRADE_LEVELS:
        rule = GRADE_THRESHOLDS.get(grade, {})
        min_score = int(rule.get("min_score", 0))
        max_score = rule.get("max_score")
        if score >= min_score and (max_score is None or score <= int(max_score)):
            return grade
    return GRADE_LEVELS[0]


def normalize_quest_item(item: dict[str, Any]) -> dict[str, Any]:
    quiz_type = str(item.get("quiz_type") or "")
    inferred_difficulty = "intro" if quiz_type == "multiple_choice" else "main"
    options = list(item.get("choices", []))
    correct_option_text = item.get("correct_choice")
    correct_option_index = (
        options.index(correct_option_text) if correct_option_text in options else None
    )
    question = item.get("question") or "질문을 더 좋게 만들어 보세요."
    return {
        "quest_id": str(item.get("item_id") or uuid4()),
        "quest_type": quiz_type,
        "difficulty": item.get("difficulty") or inferred_difficulty,
        "topic_context": item.get("topic_context") or item.get("learning_dimension") or SERVICE_NAME,
        "title": item.get("title") or question,
        "question": question,
        "original_question": item.get("original_question") or question,
        "options": options,
        "correct_option_text": correct_option_text,
        "correct_option_index": correct_option_index,
        "explanation": item.get("explanation") or "",
        "learning_point": item.get("learning_point") or "",
    }


def build_session_quests(data: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = [normalize_quest_item(item) for item in data.get("items", [])]

    intro_candidates = [
        quest
        for quest in normalized
        if quest.get("difficulty") == "intro" and quest.get("quest_type") == "multiple_choice"
    ]
    main_candidates = [
        quest
        for quest in normalized
        if quest.get("difficulty") == "main"
        and quest.get("quest_type") == "question_improvement"
    ]
    if intro_candidates and len(main_candidates) >= 2:
        return [intro_candidates[0], main_candidates[0], main_candidates[1]]

    multiple_choice = [
        quest for quest in normalized if quest.get("quest_type") == "multiple_choice"
    ]
    question_improvement = [
        quest
        for quest in normalized
        if quest.get("quest_type") == "question_improvement"
    ]
    if len(multiple_choice) >= 1 and len(question_improvement) >= 2:
        return [
            multiple_choice[0],
            question_improvement[0],
            question_improvement[1],
        ]

    raise ValueError("퀘스트를 불러오지 못했어요. multiple_choice 1개와 question_improvement 2개가 필요합니다.")


def screen_for_quest(quest: dict[str, Any], *, feedback: bool = False) -> str:
    quest_type = quest.get("quest_type")
    if quest_type == "multiple_choice":
        return SCREEN_MULTIPLE_CHOICE_RESULT if feedback else SCREEN_MULTIPLE_CHOICE
    return SCREEN_IMPROVEMENT_RESULT if feedback else SCREEN_IMPROVEMENT


def calculate_multiple_choice_score(is_correct: bool) -> int:
    rules = SCORE_RULES.get("answer_score_rules", {})
    return int(
        rules.get(
            "multiple_choice_correct" if is_correct else "multiple_choice_incorrect",
            20 if is_correct else 5,
        )
    )


def calculate_improvement_score(overall: str) -> int:
    rules = SCORE_RULES.get("answer_score_rules", {})
    defaults = {
        "excellent": 30,
        "good": 20,
        "needs_work": 10,
    }
    return int(rules.get(f"improvement_{overall}", defaults.get(overall, 10)))


def evaluate_specificity(text: str) -> str:
    cleaned = text.strip()
    marker_hit = contains_any(cleaned, SPECIFICITY_MARKERS) or bool(re.search(r"\d", cleaned))
    if len(cleaned) >= 28 and marker_hit:
        return "excellent"
    if len(cleaned) >= 18 or marker_hit:
        return "good"
    return "needs_work"


def evaluate_context(text: str) -> str:
    cleaned = text.strip()
    marker_count = sum(1 for marker in CONTEXT_MARKERS if marker in cleaned)
    if marker_count >= 2:
        return "excellent"
    if marker_count >= 1:
        return "good"
    return "needs_work"


def evaluate_purpose(text: str) -> str:
    cleaned = text.strip()
    marker_count = sum(1 for marker in PURPOSE_MARKERS if marker in cleaned)
    if marker_count >= 2 and len(cleaned) >= 22:
        return "excellent"
    if marker_count >= 1:
        return "good"
    return "needs_work"


def evaluate_improvement_question(
    user_response: str,
    original_question: str,
    topic_context: str,
) -> tuple[dict[str, str], str, int]:
    _ = original_question
    _ = topic_context

    specificity = evaluate_specificity(user_response)
    context = evaluate_context(user_response)
    purpose = evaluate_purpose(user_response)
    grades = [specificity, context, purpose]
    if all(grade == "excellent" for grade in grades):
        overall = "excellent"
    elif any(grade == "needs_work" for grade in grades):
        overall = "needs_work"
    else:
        overall = "good"

    rubric = {
        "specificity": specificity,
        "context": context,
        "purpose": purpose,
        "overall": overall,
    }
    feedback = build_improvement_feedback(rubric)
    score = calculate_improvement_score(overall)
    return rubric, feedback, score


def build_improvement_feedback(rubric: dict[str, str]) -> str:
    messages: list[str] = []
    if rubric.get("specificity") == "excellent":
        messages.append("무엇을 묻는지가 구체적으로 드러나요.")
    elif rubric.get("specificity") == "good":
        messages.append("질문의 대상은 보이지만 조건을 조금 더 넣으면 좋아요.")
    else:
        messages.append("무엇을 궁금해하는지 더 구체적으로 적어보세요.")

    if rubric.get("context") == "excellent":
        messages.append("과목이나 과제 상황이 분명해져요.")
    elif rubric.get("context") == "good":
        messages.append("맥락 단서가 일부 보이지만 상황을 더 드러낼 수 있어요.")
    else:
        messages.append("국어 숙제, 발표 준비처럼 학습 상황을 넣어보세요.")

    if rubric.get("purpose") == "excellent":
        messages.append("원하는 도움의 형태가 분명해요.")
    elif rubric.get("purpose") == "good":
        messages.append("도움 요청은 있지만 어떤 답을 원하는지 더 말해보세요.")
    else:
        messages.append("예시, 풀이, 이유처럼 원하는 도움 형태를 함께 써보세요.")

    header_map = {
        "excellent": "질문이 아주 명확해졌어요!",
        "good": "좋아졌어요!",
        "needs_work": "한 부분만 더 보완해볼까요?",
    }
    header = header_map.get(rubric.get("overall"), "좋아졌어요!")
    return truncate_feedback(f"{header} {' '.join(messages)}")


def build_multiple_choice_feedback(quest: dict[str, Any], is_correct: bool) -> str:
    base = quest.get("explanation") or "정답 선택지가 더 좋은 질문입니다."
    prefix = "정답입니다!" if is_correct else "이 질문도 좋아요."
    return truncate_feedback(f"{prefix} {base}")


def api_session_start() -> dict[str, Any]:
    data = load_quest_contents()
    session_quests = build_session_quests(data)
    response = {
        "session_id": str(uuid4()),
        "quests": session_quests,
        "user_progress": {
            "cumulative_score": st.session_state.cumulative_score,
            "current_grade": st.session_state.current_grade,
            "completed_session_count": st.session_state.completed_session_count,
        },
    }
    st.session_state.session_id = response["session_id"]
    st.session_state.session_quests = session_quests
    st.session_state.current_quest_index = 0
    st.session_state.session_score = 0
    st.session_state.last_result = None
    st.session_state.last_submission = ""
    st.session_state.session_finalized = False
    st.session_state.grade_up_event = None
    st.session_state.last_api_response = response
    st.session_state.current_screen = screen_for_quest(session_quests[0])
    return response


def api_quest_submit(user_response: Any) -> dict[str, Any]:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    is_session_complete = (
        st.session_state.current_quest_index == len(st.session_state.session_quests) - 1
    )

    if quest.get("quest_type") == "multiple_choice":
        if not isinstance(user_response, str) or user_response not in quest.get("options", []):
            return {"error_code": "E_NO_SELECTION", "error_message": "선택지를 골라주세요"}

        is_correct = user_response == quest.get("correct_option_text")
        earned_score = calculate_multiple_choice_score(is_correct)
        response = {
            "answer_id": str(uuid4()),
            "evaluation": {
                "evaluation_type": "correctness",
                "is_correct": is_correct,
                "feedback": build_multiple_choice_feedback(quest, is_correct),
            },
            "earned_score": earned_score,
            "correct_option_index": quest.get("correct_option_index"),
            "is_session_complete": is_session_complete,
        }
    else:
        if not isinstance(user_response, str) or not user_response.strip():
            return {"error_code": "E_EMPTY_INPUT", "error_message": "질문을 작성해주세요"}
        if len(user_response.strip()) < IMPROVEMENT_MIN_LENGTH:
            return {
                "error_code": "E_TOO_SHORT",
                "error_message": "조금 더 자세히 작성해주세요 (최소 10자)",
            }

        rubric, feedback, earned_score = evaluate_improvement_question(
            user_response.strip(),
            quest.get("original_question", ""),
            quest.get("topic_context", ""),
        )
        response = {
            "answer_id": str(uuid4()),
            "evaluation": {
                "evaluation_type": "rubric",
                "rubric_result": rubric,
                "feedback": feedback,
            },
            "earned_score": earned_score,
            "is_session_complete": is_session_complete,
        }

    st.session_state.session_score += int(response["earned_score"])
    st.session_state.last_result = response
    st.session_state.last_submission = user_response
    st.session_state.last_api_response = response
    st.session_state.current_screen = screen_for_quest(quest, feedback=True)
    return response


def api_session_result() -> dict[str, Any]:
    if not st.session_state.session_finalized:
        previous_grade = st.session_state.current_grade
        cumulative_score = st.session_state.cumulative_score + st.session_state.session_score
        new_grade = determine_grade(cumulative_score)
        grade_up_event = get_grade_rank(new_grade) > get_grade_rank(previous_grade)
        st.session_state.previous_grade = previous_grade
        st.session_state.cumulative_score = cumulative_score
        st.session_state.current_grade = new_grade
        st.session_state.completed_session_count += 1
        st.session_state.session_finalized = True
        st.session_state.grade_up_event = {
            "grade_up_event": grade_up_event,
            "previous_grade": previous_grade,
            "new_grade": new_grade,
        }

    grade_event = st.session_state.grade_up_event or {
        "grade_up_event": False,
        "previous_grade": st.session_state.current_grade,
        "new_grade": st.session_state.current_grade,
    }
    response = {
        "session_id": st.session_state.session_id,
        "session_score": st.session_state.session_score,
        "user_progress": {
            "cumulative_score": st.session_state.cumulative_score,
            "current_grade": st.session_state.current_grade,
            "completed_session_count": st.session_state.completed_session_count,
        },
        "grade_up_event": grade_event["grade_up_event"],
        "previous_grade": grade_event["previous_grade"],
        "new_grade": grade_event["new_grade"],
    }
    st.session_state.last_api_response = response
    return response


def render_sidebar() -> None:
    content_path = resolve_content_path()
    with st.sidebar:
        st.subheader("세션 상태")
        st.write(f"현재 화면: {st.session_state.current_screen}")
        st.write(f"현재 등급: {st.session_state.current_grade or '없음'}")
        st.write(f"누적 점수: {st.session_state.cumulative_score}")
        st.write(f"세션 점수: {st.session_state.session_score}")
        st.subheader("화면 구성")
        for screen in SCREENS:
            st.write(f"- {screen}")
        st.subheader("내부 API")
        for endpoint in API_ENDPOINTS:
            st.write(f"- {endpoint}")
        if content_path is None:
            st.caption(
                "콘텐츠 파일을 찾지 못했습니다: "
                + ", ".join(str(path) for path in CONTENT_CANDIDATE_PATHS)
            )
        else:
            st.caption(f"콘텐츠 파일: {content_path}")


def render_start_screen() -> None:
    st.title("오늘의 질문력 퀘스트")
    st.caption(SERVICE_NAME)
    st.write("3개의 퀘스트를 풀고 질문력 점수를 쌓아보세요!")
    col1, col2 = st.columns(2)
    col1.metric("현재 등급", st.session_state.current_grade or "-")
    col2.metric("누적 점수", st.session_state.cumulative_score)
    if st.button("세션 시작", type="primary"):
        try:
            api_session_start()
        except ValueError as error:
            st.error(str(error))
        else:
            st.rerun()


def render_multiple_choice_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.subheader("객관식 퀘스트")
    st.caption(
        f"퀘스트 {st.session_state.current_quest_index + 1} / "
        f"{len(st.session_state.session_quests)}"
    )
    st.write(f"학습 맥락: {quest.get('topic_context') or SERVICE_NAME}")
    st.write(f"원본 질문: {quest.get('original_question') or quest.get('question')}")
    st.info(quest.get("question") or "이 질문을 더 좋게 바꾼 선택지를 골라보세요.")
    choice_key = f"choice_{quest['quest_id']}"
    st.radio("선택지를 고르세요.", quest.get("options", []), index=None, key=choice_key)
    if st.button("제출", type="primary"):
        selected = st.session_state.get(choice_key)
        response = api_quest_submit(selected)
        if "error_code" in response:
            st.warning(response["error_message"])
        else:
            st.rerun()


def render_multiple_choice_result() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    result = st.session_state.last_result or {}
    evaluation = result.get("evaluation", {})
    is_correct = bool(evaluation.get("is_correct"))
    st.subheader("객관식 결과")
    st.success("정답입니다!" if is_correct else "이 질문도 좋아요")
    st.write(f"내가 고른 답: {st.session_state.last_submission or '미응답'}")
    st.write(f"정답: {quest.get('correct_option_text', '-')}")
    st.write(f"해설: {evaluation.get('feedback', quest.get('explanation', ''))}")
    if quest.get("learning_point"):
        st.write(f"학습 포인트: {quest['learning_point']}")
    st.write(f"획득 점수: +{result.get('earned_score', 0)}점")
    if st.button("다음 퀘스트로", type="primary"):
        st.session_state.current_quest_index += 1
        st.session_state.last_result = None
        st.session_state.last_submission = ""
        next_quest = st.session_state.session_quests[st.session_state.current_quest_index]
        st.session_state.current_screen = screen_for_quest(next_quest)
        st.rerun()


def render_improvement_screen() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    st.subheader("질문 더 좋게 만들기")
    st.caption(
        f"퀘스트 {st.session_state.current_quest_index + 1} / "
        f"{len(st.session_state.session_quests)}"
    )
    st.write(f"학습 맥락: {quest.get('topic_context') or SERVICE_NAME}")
    st.write(f"원본 질문: {quest.get('original_question') or quest.get('question')}")
    st.info("이 질문을 더 명확하게 바꿔보세요. 무엇을, 왜, 어떻게가 들어가면 좋아요.")
    text_key = f"text_{quest['quest_id']}"
    user_text = st.text_area(
        "질문 다시 쓰기",
        key=text_key,
        max_chars=IMPROVEMENT_MAX_LENGTH,
        height=180,
    )
    st.caption(f"{len(user_text)} / {IMPROVEMENT_MAX_LENGTH}")
    if st.button("제출", type="primary"):
        response = api_quest_submit(user_text.strip())
        if "error_code" in response:
            st.warning(response["error_message"])
        else:
            st.rerun()


def render_improvement_result() -> None:
    quest = st.session_state.session_quests[st.session_state.current_quest_index]
    result = st.session_state.last_result or {}
    evaluation = result.get("evaluation", {})
    rubric = evaluation.get("rubric_result", {})
    overall = rubric.get("overall", "good")
    header_map = {
        "excellent": "아주 명확해졌어요!",
        "good": "좋아졌어요!",
        "needs_work": "한 부분만 더 보완해볼까요?",
    }
    st.subheader("개선형 퀘스트 결과")
    st.success(header_map.get(overall, "좋아졌어요!"))
    col1, col2 = st.columns(2)
    col1.markdown("**Before**")
    col1.write(quest.get("original_question") or quest.get("question"))
    col2.markdown("**After**")
    col2.write(st.session_state.last_submission or "미응답")
    st.write(
        " / ".join(
            [
                f"구체성: {rubric.get('specificity', '-')}",
                f"맥락성: {rubric.get('context', '-')}",
                f"목적성: {rubric.get('purpose', '-')}",
            ]
        )
    )
    st.write(f"피드백: {evaluation.get('feedback', '')}")
    if quest.get("learning_point"):
        st.write(f"학습 포인트: {quest['learning_point']}")
    st.write(f"획득 점수: +{result.get('earned_score', 0)}점")
    button_label = (
        "결과 보기"
        if st.session_state.current_quest_index >= len(st.session_state.session_quests) - 1
        else "다음 퀘스트로"
    )
    if st.button(button_label, type="primary"):
        st.session_state.last_result = None
        st.session_state.last_submission = ""
        if st.session_state.current_quest_index >= len(st.session_state.session_quests) - 1:
            st.session_state.current_screen = SCREEN_SESSION_RESULT
        else:
            st.session_state.current_quest_index += 1
            next_quest = st.session_state.session_quests[st.session_state.current_quest_index]
            st.session_state.current_screen = screen_for_quest(next_quest)
        st.rerun()


def render_session_result() -> None:
    result = api_session_result()
    st.subheader("오늘의 퀘스트 완료!")
    col1, col2, col3 = st.columns(3)
    col1.metric("이번 세션 점수", f"+{result['session_score']}점")
    col2.metric("누적 총점", result["user_progress"]["cumulative_score"])
    col3.metric("현재 등급", result["user_progress"]["current_grade"])
    if result.get("grade_up_event"):
        st.success(f"축하해요! 이제 {result.get('new_grade')} 단계예요")
    st.write(f"완료한 세션 수: {result['user_progress']['completed_session_count']}")
    col_a, col_b = st.columns(2)
    if col_a.button("새 세션 시작", type="primary"):
        reset_session_progress()
        st.rerun()
    if col_b.button("종료"):
        reset_session_progress()
        st.rerun()


def main() -> None:
    st.set_page_config(page_title=f"{SERVICE_NAME} MVP", page_icon="🧭", layout="wide")
    ensure_state()
    render_sidebar()

    if resolve_content_path() is None:
        st.warning(
            "콘텐츠 파일을 찾지 못했습니다. 다음 경로를 확인하세요: "
            + ", ".join(str(path) for path in CONTENT_CANDIDATE_PATHS)
        )

    screen = st.session_state.current_screen
    if screen == SCREEN_START:
        render_start_screen()
    elif screen == SCREEN_MULTIPLE_CHOICE:
        render_multiple_choice_screen()
    elif screen == SCREEN_MULTIPLE_CHOICE_RESULT:
        render_multiple_choice_result()
    elif screen == SCREEN_IMPROVEMENT:
        render_improvement_screen()
    elif screen == SCREEN_IMPROVEMENT_RESULT:
        render_improvement_result()
    elif screen == SCREEN_SESSION_RESULT:
        render_session_result()
    else:
        st.error(f"알 수 없는 화면 상태입니다: {screen}")


if __name__ == "__main__":
    main()
