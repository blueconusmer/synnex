from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

OUTPUT_PATH = Path(__file__).resolve().parent / "outputs" / "quiz_contents.json"


def load_quiz_contents() -> dict[str, object]:
    if not OUTPUT_PATH.exists():
        return {}
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


def render_header(data: dict[str, object]) -> None:
    st.set_page_config(page_title="교육 서비스 MVP 데모", page_icon="📘", layout="wide")
    st.title("질문력 향상 퀴즈 서비스 MVP")
    st.caption("교육 서비스 구현 전문 AI Agent 팀이 생성한 퀴즈 MVP 데모")
    st.write(
        data.get(
            "service_summary",
            "outputs/quiz_contents.json을 읽어 문제 풀이, 정답, 해설, 학습 포인트를 보여준다.",
        )
    )


def render_sidebar(data: dict[str, object]) -> None:
    with st.sidebar:
        st.subheader("퀴즈 구성")
        for quiz_type in data.get("quiz_types", []):
            st.write(f"- {quiz_type}")
        st.subheader("생성 통계")
        st.write(f"총 문제 수: {len(data.get('items', []))}")
        st.write(f"데이터 파일: {OUTPUT_PATH}")


def render_quiz(data: dict[str, object]) -> None:
    items = data.get("items", [])
    if not items:
        st.warning("quiz_contents.json이 아직 없습니다. 먼저 파이프라인을 실행하세요.")
        st.stop()

    st.subheader("퀴즈 풀기")
    answers: dict[str, str] = {}
    for item in items:
        st.markdown(f"### {item['title']}")
        st.caption(
            f"유형: {item['quiz_type']} | 학습 차원: {item.get('learning_dimension', '미지정')}"
        )
        st.write(item["question"])
        answers[item["item_id"]] = st.radio(
            "선택지를 고르세요.",
            item["choices"],
            index=None,
            key=item["item_id"],
        )
        st.divider()

    if st.button("채점하기", type="primary"):
        score = 0
        for item in items:
            selected = answers.get(item["item_id"])
            correct = item["correct_choice"]
            if selected == correct:
                score += 1

        st.success(f"총 {len(items)}문제 중 {score}문제를 맞혔어요.")
        st.subheader("문항별 결과")
        for item in items:
            selected = answers.get(item["item_id"])
            correct = item["correct_choice"]
            is_correct = selected == correct
            status = "정답" if is_correct else "오답"
            st.markdown(f"#### {item['title']} - {status}")
            st.write(
                f"- 유형: {item['quiz_type']} / 학습 차원: {item.get('learning_dimension', '미지정')}"
            )
            st.write(f"- 내가 고른 답: {selected or '미응답'}")
            st.write(f"- 정답: {correct}")
            st.write(f"- 해설: {item['explanation']}")
            st.write(f"- 학습 포인트: {item['learning_point']}")
            st.divider()


def main() -> None:
    data = load_quiz_contents()
    render_header(data)
    render_sidebar(data)
    render_quiz(data)


main()