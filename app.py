import streamlit as st
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Configuration
APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
CONTENT_FILENAME = "question_quest_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

# Session state initialization
if "session_state" not in st.session_state:
    st.session_state.session_state = {
        "session_id": None,
        "quests": [],
        "current_quest_index": 0,
        "answers": [],
        "cumulative_score": 0,
        "current_grade": "bronze",
        "completed_session_count": 0,
        "session_score": 0,
        "is_session_complete": False,
        "grade_up_event": False,
        "previous_grade": None,
        "new_grade": None
    }

# Helper functions

def resolve_content_path() -> Optional[Path]:
    """Returns the first existing content file path or None if none exist"""
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None

def load_content(path: Path) -> Dict[str, Any]:
    """Loads and returns the content JSON file"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def determine_grade(score: int) -> str:
    """Determines the user's grade based on cumulative score"""
    if score >= 600:
        return "platinum"
    elif score >= 300:
        return "gold"
    elif score >= 100:
        return "silver"
    else:
        return "bronze"

def evaluate_improvement_question(
    user_response: str,
    original_question: str,
    topic_context: str
) -> Tuple[Dict[str, str], str, int]:
    """Evaluates an improvement question using rule-based heuristics"""
    # Simple keyword-based evaluation
    specificity_keywords = ["무엇", "어떻게", "왜", "어떤", "어떤 점에서", "어떤 부분에서"]
    context_keywords = ["숙제", "시험", "과제", "수업", "공부", "학교", "집", "학원"]
    purpose_keywords = ["설명", "예시", "풀이", "알려줘", "알려주세요", "설명해줘", "설명해주세요"]

    specificity_score = sum(1 for keyword in specificity_keywords if keyword in user_response)
    context_score = sum(1 for keyword in context_keywords if keyword in topic_context or keyword in user_response)
    purpose_score = sum(1 for keyword in purpose_keywords if keyword in user_response)

    rubric_result = {
        "specificity": "excellent" if specificity_score >= 2 else "good" if specificity_score == 1 else "needs_work",
        "context": "excellent" if context_score >= 2 else "good" if context_score == 1 else "needs_work",
        "purpose": "excellent" if purpose_score >= 2 else "good" if purpose_score == 1 else "needs_work",
        "overall": "excellent" if all(
            s == "excellent" for s in [
                "excellent" if specificity_score >= 2 else "good" if specificity_score == 1 else "needs_work",
                "excellent" if context_score >= 2 else "good" if context_score == 1 else "needs_work",
                "excellent" if purpose_score >= 2 else "good" if purpose_score == 1 else "needs_work"
            ]
        ) else "needs_work" if any(
            s == "needs_work" for s in [
                "excellent" if specificity_score >= 2 else "good" if specificity_score == 1 else "needs_work",
                "excellent" if context_score >= 2 else "good" if context_score == 1 else "needs_work",
                "excellent" if purpose_score >= 2 else "good" if purpose_score == 1 else "needs_work"
            ]
        ) else "good"
    }

    if rubric_result["overall"] == "excellent":
        feedback = "질문이 아주 명확해졌어요! 무엇을, 왜, 어떻게가 모두 잘 드러나 있어요."
        score = 30
    elif rubric_result["overall"] == "needs_work":
        feedback = "한 부분이 더 명확해지면 좋겠어요. "
        if rubric_result["specificity"] == "needs_work":
            feedback += "무엇을 묻는지 더 명확히 해주세요."
        elif rubric_result["context"] == "needs_work":
            feedback += "왜 필요한지 상황을 더 명확히 해주세요."
        else:
            feedback += "어떤 도움을 원하는지 더 명확히 해주세요."
        score = 10
    else:  # good
        feedback = "좋아졌어요! "
        if rubric_result["specificity"] == "excellent":
            feedback += "무엇을 묻는지 명확해졌어요."
        elif rubric_result["context"] == "excellent":
            feedback += "왜 필요한지 명확해졌어요."
        else:
            feedback += "어떤 도움을 원하는지 명확해졌어요."
        score = 20

    return rubric_result, feedback, score

# API functions
def api_session_start(user_id: str = "anonymous") -> Dict[str, Any]:
    """Simulates session start API call"""
    session_id = f"session_{st.session_state.session_state['completed_session_count'] + 1}"

    # Get quests from content
    content = load_content(resolve_content_path())
    quests = content["items"][:3]  # Take first 3 quests

    return {
        "session_id": session_id,
        "quests": quests,
        "user_progress": {
            "cumulative_score": st.session_state.session_state["cumulative_score"],
            "current_grade": st.session_state.session_state["current_grade"],
            "completed_session_count": st.session_state.session_state["completed_session_count"]
        }
    }

def api_quest_submit(
    session_id: str,
    quest_id: str,
    user_response: Any,
    quest_type: str
) -> Dict[str, Any]:
    """Simulates quest submit API call"""
    answer_id = f"ans_{len(st.session_state.session_state['answers']) + 1}"
    quest = next(q for q in st.session_state.session_state["quests"] if q["item_id"] == quest_id)

    if quest_type == "multiple_choice":
        # Handle multiple choice
        correct_index = int(quest["correct_choice"][0]) if isinstance(quest["correct_choice"], str) and quest["correct_choice"].startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')) else 0
        is_correct = int(user_response) == correct_index

        if is_correct:
            feedback = f"정답입니다! {quest['explanation']}"
            earned_score = 20
        else:
            feedback = f"이 질문도 좋지만 더 명확한 선택지가 있어요. {quest['explanation']}"
            earned_score = 5

        evaluation = {
            "evaluation_type": "correctness",
            "is_correct": is_correct,
            "feedback": feedback
        }
    else:  # question_improvement
        # Handle question improvement
        rubric_result, feedback, earned_score = evaluate_improvement_question(
            user_response,
            quest["original_question"],
            quest["topic_context"],
            quest["desired_answer_form"]
        )

        evaluation = {
            "evaluation_type": "rubric",
            "rubric_result": rubric_result,
            "feedback": feedback
        }

    # Update session state
    st.session_state.session_state["session_score"] += earned_score
    is_session_complete = (st.session_state.session_state["current_quest_index"] + 1) == len(st.session_state.session_state["quests"])

    return {
        "answer_id": answer_id,
        "evaluation": evaluation,
        "earned_score": earned_score,
        "is_session_complete": is_session_complete
    }

def api_session_result(session_id: str) -> Dict[str, Any]:
    """Simulates session result API call"""
    previous_grade = st.session_state.session_state["current_grade"]
    st.session_state.session_state["cumulative_score"] += st.session_state.session_state["session_score"]
    st.session_state.session_state["completed_session_count"] += 1
    new_grade = determine_grade(st.session_state.session_state["cumulative_score"])
    st.session_state.session_state["current_grade"] = new_grade
    st.session_state.session_state["grade_up_event"] = (new_grade != previous_grade)
    st.session_state.session_state["previous_grade"] = previous_grade
    st.session_state.session_state["new_grade"] = new_grade

    return {
        "session_id": session_id,
        "session_score": st.session_state.session_state["session_score"],
        "user_progress": {
            "cumulative_score": st.session_state.session_state["cumulative_score"],
            "current_grade": new_grade,
            "completed_session_count": st.session_state.session_state["completed_session_count"]
        },
        "grade_up_event": st.session_state.session_state["grade_up_event"],
        "previous_grade": previous_grade,
        "new_grade": new_grade
    }

# Main app
def main():
    """Main function for the Streamlit app"""
    st.set_page_config(page_title="질문력 퀘스트", page_icon="\ud83d\udcac")

    # Check if content file exists
    content_path = resolve_content_path()
    if not content_path:
        st.error("콘텐츠 파일을 찾을 수 없습니다. 'outputs/question_quest_contents.json' 또는 루트 디렉토리에 'question_quest_contents.json' 파일이 있는지 확인하세요.")
        return

    # Load content
    content = load_content(content_path)

    # Session state
    ss = st.session_state.session_state

    # Session start
    if "session_started" not in st.session_state or not st.session_state.session_started:
        st.session_state.session_started = True
        api_response = api_session_start()
        ss["session_id"] = api_response["session_id"]
        ss["quests"] = api_response["quests"]
        ss["cumulative_score"] = api_response["user_progress"]["cumulative_score"]
        ss["current_grade"] = api_response["user_progress"]["current_grade"]
        ss["completed_session_count"] = api_response["user_progress"]["completed_session_count"]
        ss["session_score"] = 0
        ss["current_quest_index"] = 0
        ss["is_session_complete"] = False
        ss["grade_up_event"] = False
        ss["previous_grade"] = None
        ss["new_grade"] = None

    # Application views
    if ss["is_session_complete"]:
        # Session result view (S5)
        result_data = api_session_result(ss["session_id"])

        st.header("📊 오늘의 퀘스트 완료!")
        st.subheader(f"이번 세션: +{result_data['session_score']}점")
        st.subheader(f"전체 누적: {result_data['user_progress']['cumulative_score']}점")
        st.subheader(f"현재 등급: {result_data['user_progress']['current_grade']}")

        if result_data["grade_up_event"]:
            st.success(f"축하해요! 이제 {result_data['new_grade']} 단계예요 \ud83c\udf89")

        if st.button("새 세션 시작"):
            st.session_state.session_started = False
            st.experimental_rerun()

        st.button("종료")
    else:
        current_quest = ss["quests"][ss["current_quest_index"]]
        quest_type = current_quest["quiz_type"]

        # Progress display
        st.sidebar.header(f"퀘스트 {ss['current_quest_index'] + 1} / 3")
        st.sidebar.metric("누적 점수", ss["cumulative_score"])
        st.sidebar.metric("현재 등급", ss["current_grade"])

        if quest_type == "multiple_choice":
            # Multiple choice view (S1)
            st.header("🧩 더 좋은 질문 고르기")
            st.write(f"학습 맥락: {current_quest['topic_context']}")
            st.write(f"원본 질문: {current_quest['original_question']}")
            st.write("이 질문을 더 좋게 바꾼 선택지는 무엇일까요?")

            choices = current_quest["choices"]
            selected_choice = st.radio("선택지", choices, key="multiple_choice", index=None, horizontal=True)

            if st.button("제출"):
                if selected_choice is None:
                    st.warning("선택지를 골라주세요")
                else:
                    user_response = choices.index(selected_choice)
                    api_response = api_quest_submit(
                        ss["session_id"],
                        current_quest["item_id"],
                        user_response,
                        quest_type
                    )

                    ss["answers"].append({
                        "answer_id": api_response["answer_id"],
                        "evaluation": api_response["evaluation"],
                        "earned_score": api_response["earned_score"],
                        "correct_option_index": current_quest["correct_choice"] if isinstance(current_quest["correct_choice"], str) and current_quest["correct_choice"].startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')) else 0
                    })

                    ss["current_quest_index"] += 1
                    ss["is_session_complete"] = api_response["is_session_complete"]
                    st.experimental_rerun()
        else:  # question_improvement
            # Question improvement view (S3)
            st.header("✏️ 질문 더 좋게 만들기")
            st.write(f"학습 맥락: {current_quest['topic_context']}")
            st.write(f"원본 질문: {current_quest['original_question']}")
            st.write("이 질문을 더 명확하게 바꿔보세요. 무엇을, 왜, 어떻게가 들어가면 좋아요.")

            user_response = st.text_area(
                "개선된 질문",
                key="question_improvement",
                placeholder="질문을 작성해주세요 (최소 10자)",
                help="최소 10자 이상 작성해주세요"
            )

            if st.button("제출"):
                if len(user_response.strip()) < 10:
                    st.warning("조금 더 자세히 작성해주세요 (최소 10자)")
                else:
                    api_response = api_quest_submit(
                        ss["session_id"],
                        current_quest["item_id"],
                        user_response,
                        quest_type
                    )

                    ss["answers"].append({
                        "answer_id": api_response["answer_id"],
                        "evaluation": api_response["evaluation"],
                        "earned_score": api_response["earned_score"],
                        "user_response": user_response
                    })

                    ss["current_quest_index"] += 1
                    ss["is_session_complete"] = api_response["is_session_complete"]
                    st.experimental_rerun()

    # Feedback view for completed quests
    if len(ss["answers"]) > 0 and not ss["is_session_complete"]:
        last_answer = ss["answers"][-1]
        quest = ss["quests"][ss["current_quest_index"] - 1]

        st.header("📝 결과 확인")

        if quest["quiz_type"] == "multiple_choice":
            # Multiple choice feedback (S2)
            if last_answer["evaluation"]["is_correct"]:
                st.success("✅ 정답입니다!")
            else:
                st.info("❌ 이 질문도 좋아요")

            st.write(f"선택한 답변: {quest['choices'][int(last_answer['user_response'])]}")
            st.write(f"정답: {quest['choices'][last_answer['correct_option_index']]}")
            st.write(f"해설: {last_answer['evaluation']['feedback']}")
            st.write(f"획득 점수: +{last_answer['earned_score']}점")

            if st.button("다음 퀘스트로"):
                st.experimental_rerun()
        else:  # question_improvement
            # Question improvement feedback (S4)
            overall = last_answer["evaluation"]["rubric_result"]["overall"]

            if overall == "excellent":
                st.success("🎉 아주 명확해졌어요!")
            elif overall == "needs_work":
                st.warning("⚠️ 한 부분이 더 명확해지면 좋겠어요")
            else:  # good
                st.info("👍 좋아졌어요!")

            st.write(f"Before: {quest['original_question']}")
            st.write(f"After: {last_answer['user_response']}")

            rubric = last_answer["evaluation"]["rubric_result"]
            st.write("루브릭 결과:")
            st.write(f"- 구체성: {rubric['specificity']}")
            st.write(f"- 맥락성: {rubric['context']}")
            st.write(f"- 목적성: {rubric['purpose']}")
            st.write(f"- 종합: {rubric['overall']}")
            st.write(f"피드백: {last_answer['evaluation']['feedback']}")
            st.write(f"획득 점수: +{last_answer['earned_score']}점")

            if st.button("다음 퀘스트로" if ss["current_quest_index"] < len(ss["quests"]) else "결과 보기"):
                st.experimental_rerun()

if __name__ == "__main__":
    main()
