from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

CONTENT_FILENAME = "Question_Coaching_Chatbot_contents.json"
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


def describe_content_paths() -> str:
    return ", ".join(str(path) for path in CONTENT_CANDIDATE_PATHS)


def load_interaction_contents() -> dict[str, Any]:
    content_path = resolve_content_path()
    if content_path is None:
        return {}
    return json.loads(content_path.read_text(encoding="utf-8"))


def find_unit(interaction_type: str) -> dict[str, Any]:
    for unit in st.session_state.interaction_units:
        if unit.get("interaction_type") == interaction_type:
            return unit
    return {}


def ensure_state() -> None:
    defaults = {
        "current_screen": SCREEN_START,
        "interaction_units": [],
        "evaluation_rules": {},
        "turn_count": 0,
        "last_input": "",
        "diagnosis_mode": "",
        "follow_up_message": "",
        "improved_question": "",
        "last_error": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def contains_any(text: str, markers: list[str]) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in markers)


def detect_missing_dimension(user_input: str) -> str:
    lowered = user_input.lower()
    if len(lowered.strip()) < 10:
        return "need_specificity"
    if not contains_any(lowered, ["국어", "수학", "과학", "사회", "발표", "숙제", "수행평가", "과제"]):
        return "need_context"
    if not contains_any(lowered, ["이유", "방법", "설명", "예시", "도와", "알고 싶", "비교"]):
        return "need_purpose"
    return "completed"


def build_follow_up_message(mode: str) -> str:
    unit = find_unit("coaching_feedback")
    default_messages = {
        "need_specificity": "무엇이 궁금한지 조금 더 구체적으로 적어볼래요?",
        "need_context": "어떤 과목이나 상황인지 함께 적어볼래요?",
        "need_purpose": "무엇을 알고 싶은지 한 문장으로 덧붙여볼래요?",
    }
    return (
        unit.get("system_response")
        or default_messages.get(mode)
        or "질문을 한 번 더 구체적으로 적어볼래요?"
    )


def build_improved_question(user_input: str, mode: str) -> str:
    suffix = {
        "need_specificity": "핵심 개념과 범위를 포함해 설명해줘.",
        "need_context": "과목과 상황을 반영해서 설명해줘.",
        "need_purpose": "내가 왜 이 질문을 하는지 고려해서 설명해줘.",
        "completed": "내 상황에 맞는 답을 예시와 함께 설명해줘.",
    }.get(mode, "조금 더 자세히 설명해줘.")
    return f"{user_input.strip()} {suffix}".strip()


def api_session_start() -> dict[str, Any]:
    data = load_interaction_contents()
    st.session_state.interaction_units = data.get("interaction_units", [])
    st.session_state.evaluation_rules = data.get("evaluation_rules", {})
    st.session_state.turn_count = 0
    st.session_state.last_input = ""
    st.session_state.diagnosis_mode = ""
    st.session_state.follow_up_message = ""
    st.session_state.improved_question = ""
    st.session_state.last_error = ""
    st.session_state.current_screen = SCREEN_INPUT
    return {
        "session_id": "coaching-session",
        "interaction_units": st.session_state.interaction_units,
    }


def api_chat_submit(user_response: str) -> dict[str, Any]:
    if not user_response.strip():
        st.session_state.last_error = "질문을 입력해주세요."
        st.session_state.current_screen = SCREEN_ERROR
        return {"mode": "error", "next_action": "ask_more"}

    st.session_state.last_input = user_response.strip()
    st.session_state.turn_count += 1
    mode = detect_missing_dimension(st.session_state.last_input)
    if st.session_state.turn_count >= 2:
        mode = "completed"

    st.session_state.diagnosis_mode = mode
    st.session_state.improved_question = build_improved_question(
        st.session_state.last_input,
        mode,
    )
    if mode == "completed":
        st.session_state.current_screen = SCREEN_RESULT
        return {"mode": mode, "next_action": "show_result"}

    st.session_state.follow_up_message = build_follow_up_message(mode)
    st.session_state.current_screen = SCREEN_FOLLOW_UP
    return {"mode": mode, "next_action": "ask_more"}


def api_session_result() -> dict[str, Any]:
    return {
        "original_question": st.session_state.last_input,
        "improved_question": st.session_state.improved_question,
        "diagnosis_mode": st.session_state.diagnosis_mode,
        "turn_count": st.session_state.turn_count,
    }


def render_input_screen() -> None:
    unit = find_unit("free_text_input")
    st.subheader(unit.get("title") or "질문 입력")
    if unit.get("system_response"):
        st.write(unit.get("system_response"))
    user_text = st.text_area("질문을 입력하세요", key="chat_input")
    if st.button("진단하기", type="primary") and user_text.strip():
        api_chat_submit(user_text)
        st.rerun()


def render_follow_up_screen() -> None:
    st.subheader("되묻기")
    st.write(st.session_state.follow_up_message or "한 번 더 구체적으로 적어볼래요?")
    follow_up = st.text_area("보완한 질문", key="follow_up_input")
    if st.button("다시 진단하기", type="primary") and follow_up.strip():
        api_chat_submit(follow_up)
        st.rerun()


def render_result_screen() -> None:
    result = api_session_result()
    st.subheader("개선 결과")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 원래 질문")
        st.caption(result.get("original_question", ""))
    with col2:
        st.markdown("### 개선된 질문")
        st.caption(result.get("improved_question", ""))
    st.write(f"진단 모드: {result.get('diagnosis_mode', 'completed')}")
    if st.button("다시 시작"):
        api_session_start()
        st.rerun()


def render_error_screen() -> None:
    st.warning(st.session_state.last_error or "입력을 확인해주세요.")
    if st.button("입력 화면으로 돌아가기"):
        st.session_state.current_screen = SCREEN_INPUT
        st.rerun()


def main() -> None:
    data = load_interaction_contents()
    st.set_page_config(page_title="Question Coaching Chatbot MVP 데모", page_icon="💬", layout="wide")
    st.title("Question Coaching Chatbot MVP")
    st.caption("interaction_units 기반 코칭 챗봇 MVP")
    if not data:
        st.warning(
            "콘텐츠 파일을 찾지 못했습니다. "
            f"다음 경로 중 하나에 파일을 준비하세요: {describe_content_paths()}"
        )
        st.stop()

    ensure_state()
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
        st.error(f"알 수 없는 화면 상태입니다: {st.session_state.current_screen}")


main()
