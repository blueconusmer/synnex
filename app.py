from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
CRITERIA_LABELS = {
    "specificity": "구체성",
    "context": "맥락성",
    "purpose": "목적성",
}
GENERIC_KEYWORDS = ["이거", "그거", "저거", "이 내용", "그 내용", "이 문제", "그 문제"]
CONTEXT_KEYWORDS = [
    "숙제",
    "수업",
    "시험",
    "과제",
    "발표",
    "글쓰기",
    "문제집",
    "학교",
    "국어",
    "수학",
    "과학",
    "영어",
    "사회",
    "역사",
]
PURPOSE_KEYWORDS = [
    "설명",
    "예시",
    "힌트",
    "비교",
    "정리",
    "답",
    "도와",
    "알려",
    "왜",
    "어떻게",
]
TOPIC_KEYWORDS = [
    "비유",
    "문학",
    "시",
    "소설",
    "문법",
    "함수",
    "방정식",
    "분수",
    "과학",
    "실험",
    "역사",
    "영어",
]


@dataclass
class QuestionDiagnosis:
    focus: str
    follow_up_prompt: str
    before_scores: dict[str, bool]


def load_demo_artifacts() -> dict[str, object]:
    """Load pipeline artifacts from outputs with fallback data."""

    loaded_files: list[str] = []
    missing_files: list[str] = []

    planner = _load_json("planner_output.json", loaded_files, missing_files) or {
        "project_goal": "질문력 Co-Learner 제작용 AI 팀 설계",
        "target_user": "중학생 질문 개선 챗봇 사용자",
        "mvp_scope": [
            "질문 Before / After 개선 경험 보여주기",
            "질문 개선 기준을 반영한 최소 데모 구성",
        ],
    }
    question = _load_json("question_output.json", loaded_files, missing_files) or {
        "agent_role": "질문을 더 구체적이고 맥락 있게 다듬어 주는 질문 튜터",
        "core_principles": [
            "Increase specificity in every learner question.",
            "Expose the learning context behind the question.",
            "Clarify what kind of help the learner wants.",
        ],
        "few_shot_examples": [
            {
                "user_question": "비유가 뭔지 모르겠어.",
                "assistant_guidance": "국어 숙제인지, 어떤 문장이 나왔는지 한 번만 더 물어본다.",
            }
        ],
    }
    quest = _load_json("quest_output.json", loaded_files, missing_files) or {
        "sample_quests": [
            {"title": "질문에서 빠진 요소 찾기"},
            {"title": "모호한 질문 다시 쓰기"},
        ]
    }
    growth = _load_json("growth_output.json", loaded_files, missing_files) or {
        "scoring_rules": [
            {"criterion": "specificity"},
            {"criterion": "context"},
            {"criterion": "purpose"},
        ],
        "feedback_templates": [
            {"condition": "specificity improved"},
            {"condition": "context improved"},
            {"condition": "purpose improved"},
        ],
    }

    summary_path = OUTPUT_DIR / "final_summary.md"
    if summary_path.exists():
        loaded_files.append("final_summary.md")
        final_summary = summary_path.read_text(encoding="utf-8")
    else:
        missing_files.append("final_summary.md")
        final_summary = "아직 파이프라인 요약 파일이 없습니다."

    return {
        "planner": planner,
        "question": question,
        "quest": quest,
        "growth": growth,
        "final_summary": final_summary,
        "loaded_files": loaded_files,
        "missing_files": missing_files,
    }


def _load_json(
    file_name: str,
    loaded_files: list[str],
    missing_files: list[str],
) -> dict[str, object] | None:
    path = OUTPUT_DIR / file_name
    if not path.exists():
        missing_files.append(file_name)
        return None

    loaded_files.append(file_name)
    return json.loads(path.read_text(encoding="utf-8"))


def initialize_state(artifacts: dict[str, object]) -> None:
    """Initialize Streamlit session state for the demo chat."""

    if "messages" in st.session_state:
        return

    reset_demo_state(artifacts)


def reset_demo_state(artifacts: dict[str, object]) -> None:
    """Reset the demo conversation to its initial state."""

    target_user = artifacts["planner"].get("target_user", "중학생")
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                f"{target_user}를 위한 질문 튜터 데모야. 모호한 질문을 입력하면 한 번 되묻고, "
                "더 좋은 질문으로 바꿔볼게."
            ),
        }
    ]
    st.session_state.phase = "await_before"
    st.session_state.before_question = ""
    st.session_state.follow_up_prompt = ""
    st.session_state.focus = ""
    st.session_state.result = None


def evaluate_question(text: str) -> dict[str, bool]:
    """Evaluate whether a question shows specificity, context, and purpose."""

    cleaned = normalize_text(text)
    lower = cleaned.lower()
    has_quote_or_example = any(symbol in cleaned for symbol in ["'", '"', "“", "”", "‘", "’"])
    specificity = (
        len(cleaned) >= 8
        and not any(keyword in cleaned for keyword in GENERIC_KEYWORDS)
        and (
            has_quote_or_example
            or any(keyword in cleaned for keyword in TOPIC_KEYWORDS)
            or len(cleaned.split()) >= 4
        )
    )
    context = any(keyword in cleaned for keyword in CONTEXT_KEYWORDS)
    purpose = any(keyword in lower for keyword in PURPOSE_KEYWORDS) or any(
        token in cleaned for token in ["왜", "어떻게", "무엇", "뭔지"]
    )

    return {
        "specificity": specificity,
        "context": context,
        "purpose": purpose,
    }


def diagnose_question(question: str) -> QuestionDiagnosis:
    """Pick the most useful single follow-up focus for the demo."""

    scores = evaluate_question(question)
    if not scores["specificity"] or any(keyword in question for keyword in GENERIC_KEYWORDS):
        focus = "specificity"
    elif not scores["context"]:
        focus = "context"
    elif not scores["purpose"]:
        focus = "purpose"
    else:
        focus = "context"

    return QuestionDiagnosis(
        focus=focus,
        follow_up_prompt=build_follow_up_prompt(question, focus),
        before_scores=scores,
    )


def build_follow_up_prompt(question: str, focus: str) -> str:
    """Create a single clarifying follow-up question."""

    if focus == "context":
        subject = detect_subject(question)
        if subject == "korean":
            return "질문을 더 맥락이 보이게 만들려면, 국어 숙제인지 수업 시간 내용인지 알려줄래?"
        if subject == "math":
            return "질문을 더 맥락이 보이게 만들려면, 수학 숙제인지 어떤 단원 문제인지 알려줄래?"
        if subject == "science":
            return "질문을 더 맥락이 보이게 만들려면, 과학 숙제인지 어떤 개념이나 실험인지 알려줄래?"
        return "질문을 더 맥락이 보이게 만들려면, 어떤 과목이나 상황에서 나온 질문인지 알려줄래?"

    if focus == "specificity":
        return "질문을 더 구체적으로 만들려면, 어떤 개념·문장·문제가 헷갈리는지 한 번만 더 알려줄래?"

    return "질문을 더 원하는 도움이 드러나게 만들려면, 설명·예시·힌트 중 어떤 도움을 받고 싶은지 알려줄래?"


def detect_subject(question: str) -> str:
    """Detect a rough subject hint from the user's question."""

    if any(token in question for token in ["국어", "비유", "문학", "시", "소설", "글쓰기"]):
        return "korean"
    if any(token in question for token in ["수학", "함수", "방정식", "분수", "공식", "그래프"]):
        return "math"
    if any(token in question for token in ["과학", "실험", "생물", "화학", "물리"]):
        return "science"
    return "general"


def build_improved_question(before_question: str, added_detail: str, focus: str) -> str:
    """Create a deterministic improved question from the second user input."""

    before = normalize_text(before_question)
    detail = normalize_text(added_detail)

    if looks_like_complete_question(before, detail):
        return detail

    if focus == "context":
        prefix = detail.rstrip(".!?")
        if prefix.endswith(("야", "요")):
            prefix = f"{prefix}인데"
        elif not prefix.endswith(("인데", "중인데", "이라서", "라서")):
            prefix = f"{prefix}인 상황에서"
        return normalize_text(f"{prefix} {before}")

    if focus == "specificity":
        base = before
        for keyword in GENERIC_KEYWORDS:
            base = base.replace(keyword, "").strip()
        if not base or base in {"모르겠어", "잘 모르겠어", "헷갈려", "어려워"}:
            return normalize_text(f"{detail}가 잘 이해되지 않아.")
        return normalize_text(f"{detail}에 대해 {base}")

    if any(keyword in detail for keyword in PURPOSE_KEYWORDS):
        return normalize_text(f"{before.rstrip('.!?')} {detail}")

    return normalize_text(f"{before.rstrip('.!?')} 그리고 {detail}")


def looks_like_complete_question(before_question: str, added_detail: str) -> bool:
    """Heuristic: treat the second answer as final if it already looks complete."""

    if len(added_detail) <= len(before_question):
        return False

    detail_scores = evaluate_question(added_detail)
    return detail_scores["context"] and (detail_scores["specificity"] or detail_scores["purpose"])


def build_feedback(
    before_question: str,
    after_question: str,
    growth_artifacts: dict[str, object],
) -> tuple[str, list[str]]:
    """Build a one-line feedback message and improved criteria list."""

    before_scores = evaluate_question(before_question)
    after_scores = evaluate_question(after_question)
    criteria_order = [
        rule.get("criterion", "")
        for rule in growth_artifacts.get("scoring_rules", [])
        if rule.get("criterion")
    ] or ["specificity", "context", "purpose"]
    improved = [
        criterion
        for criterion in criteria_order
        if after_scores.get(criterion) and not before_scores.get(criterion)
    ]

    if "specificity" in improved and "context" in improved:
        return (
            "질문의 주제와 상황이 더 분명해져서 정확한 설명을 들을 수 있어.",
            improved,
        )
    if "specificity" in improved:
        return ("질문의 주제가 더 구체적이어서 무엇을 묻는지 훨씬 선명해졌어.", improved)
    if "context" in improved:
        return ("질문의 상황이 더 분명해져서 필요한 도움을 정확히 받을 수 있어.", improved)
    if "purpose" in improved:
        return ("어떤 도움을 원하는지 보여줘서 답변 방향이 더 또렷해졌어.", improved)
    return ("질문이 한 단계 정리돼서 답을 주는 사람이 이해하기 쉬워졌어.", improved)


def build_praise(improved_criteria: list[str]) -> str:
    """Return a lightweight praise message for the learner."""

    if len(improved_criteria) >= 2:
        return "좋아졌어! 이제 누가 봐도 더 도와주기 쉬운 질문이야."
    if improved_criteria:
        return "좋아! 질문이 한 단계 더 선명해졌어."
    return "좋아, 질문의 방향이 조금 더 분명해졌어."


def normalize_text(text: str) -> str:
    """Normalize whitespace for display."""

    return re.sub(r"\s+", " ", text).strip()


def process_user_input(user_input: str, artifacts: dict[str, object]) -> None:
    """Advance the demo chat by one step."""

    cleaned = normalize_text(user_input)
    if not cleaned:
        return

    if st.session_state.phase == "done":
        reset_demo_state(artifacts)

    st.session_state.messages.append({"role": "user", "content": cleaned})

    if st.session_state.phase == "await_before":
        diagnosis = diagnose_question(cleaned)
        st.session_state.before_question = cleaned
        st.session_state.follow_up_prompt = diagnosis.follow_up_prompt
        st.session_state.focus = diagnosis.focus
        st.session_state.phase = "await_detail"
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": diagnosis.follow_up_prompt,
            }
        )
        return

    after_question = build_improved_question(
        before_question=st.session_state.before_question,
        added_detail=cleaned,
        focus=st.session_state.focus,
    )
    feedback, improved_criteria = build_feedback(
        before_question=st.session_state.before_question,
        after_question=after_question,
        growth_artifacts=artifacts["growth"],
    )
    praise = build_praise(improved_criteria)

    st.session_state.result = {
        "before": st.session_state.before_question,
        "after": after_question,
        "feedback": feedback,
        "praise": praise,
        "improved_criteria": improved_criteria,
    }
    st.session_state.phase = "done"
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "좋아, 질문이 더 나아졌어. 아래 개선 결과에서 Before / After를 확인해봐.",
        }
    )


def render_sidebar(artifacts: dict[str, object]) -> None:
    """Render contextual information from the pipeline outputs."""

    planner = artifacts["planner"]
    question = artifacts["question"]
    quest = artifacts["quest"]

    with st.sidebar:
        st.subheader("Demo Context")
        st.write("기준 문서: `docs/project_context.md`")
        st.write(f"대상 사용자: {planner.get('target_user', '중학생 질문 개선 챗봇 사용자')}")

        st.markdown("**활용한 outputs 파일**")
        for file_name in artifacts["loaded_files"]:
            st.write(f"- {file_name}")

        if artifacts["missing_files"]:
            st.warning(
                "일부 outputs 파일이 없어 fallback 설정으로 데모를 보완하고 있어. "
                "필요하면 `.venv/bin/python main.py`를 먼저 실행해줘."
            )

        st.markdown("**질문 개선 기준**")
        for principle in question.get("core_principles", []):
            st.write(f"- {principle}")

        st.markdown("**샘플 퀘스트**")
        for sample in quest.get("sample_quests", [])[:2]:
            st.write(f"- {sample.get('title', '샘플 퀘스트')}")

        with st.expander("파이프라인 요약 보기"):
            st.markdown(artifacts["final_summary"])


def render_result(result: dict[str, object]) -> None:
    """Render the Before / After result card."""

    st.divider()
    st.subheader("개선 결과")

    before_col, after_col = st.columns(2)
    with before_col:
        st.markdown("#### Before 질문")
        st.error(result["before"])
    with after_col:
        st.markdown("#### After 질문")
        st.success(result["after"])

    st.markdown("#### 개선 기준")
    criterion_cols = st.columns(3)
    improved = set(result["improved_criteria"])
    order = ["specificity", "context", "purpose"]
    for column, criterion in zip(criterion_cols, order, strict=True):
        label = CRITERIA_LABELS[criterion]
        status = "향상됨" if criterion in improved else "보완 가능"
        emoji = "✅" if criterion in improved else "▫️"
        with column:
            st.markdown(f"**{label}**")
            st.write(f"{emoji} {status}")

    st.info(result["feedback"])
    st.success(result["praise"])


def main() -> None:
    st.set_page_config(
        page_title="질문력 Co-Learner Demo",
        page_icon="💬",
        layout="wide",
    )

    artifacts = load_demo_artifacts()
    initialize_state(artifacts)

    planner = artifacts["planner"]
    question = artifacts["question"]
    example_question = question.get("few_shot_examples", [{}])[0].get(
        "user_question",
        "비유가 뭔지 모르겠어.",
    )

    st.title("질문력 Co-Learner Demo")
    st.caption(
        f"{planner.get('target_user', '중학생')}를 위한 최소 Streamlit 데모야. "
        "모호한 질문을 한 번 더 다듬어 Before / After 개선 경험을 보여줘."
    )
    st.write(
        "사용자가 질문을 입력하면 질문 튜터가 한 번 되묻고, "
        "구체성·맥락성·목적성을 기준으로 더 나은 질문으로 바꿔줘."
    )
    st.write(f"예시 시작 질문: `{example_question}`")

    render_sidebar(artifacts)

    top_col, reset_col = st.columns([6, 1])
    with top_col:
        st.markdown("### 대화")
    with reset_col:
        if st.button("새 질문", use_container_width=True):
            reset_demo_state(artifacts)
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.result:
        render_result(st.session_state.result)

    placeholder = (
        "모호한 질문을 입력해봐."
        if st.session_state.phase == "await_before"
        else "되묻기에 대한 추가 정보를 입력해줘."
    )
    user_input = st.chat_input(placeholder)
    if user_input:
        process_user_input(user_input, artifacts)
        st.rerun()


if __name__ == "__main__":
    main()
