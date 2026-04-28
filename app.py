import streamlit as st
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Configuration
APP_DIR = Path(__file__).parent
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
        "user_progress": {
            "cumulative_score": 0,
            "current_grade": "bronze",
            "completed_session_count": 0
        },
        "session_score": 0,
        "answers": []
    }

# Content loading
@st.cache_data(show_spinner=False)
def load_content() -> Dict[str, Any]:
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    st.error(f"콘텐츠 파일을 찾을 수 없습니다. 다음 경로에 파일이 있는지 확인하세요: {', '.join(str(p) for p in CONTENT_CANDIDATE_PATHS)}")
    return {}

# Content loading
content = load_content()
items = content.get("items", [])
answer_key = content.get("answer_key", {})
explanations = content.get("explanations", {})
learning_points = content.get("learning_points", {})

# Helper functions

def resolve_content_path() -> Optional[Path]:
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None

def determine_grade(score: int) -> str:
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
    # Rule-based evaluation instead of LLM
    specificity_score = 0
    context_score = 0
    purpose_score = 0

    # Specificity check
    if any(keyword in user_response.lower() for keyword in ["무엇", "어떤", "어떤 것", "어떤 개념"]):
        specificity_score += 1
    if any(keyword in user_response.lower() for keyword in ["구체적으로", "명확하게", "자세히"]):
        specificity_score += 1

    # Context check
    if any(keyword in user_response.lower() for keyword in ["숙제", "시험", "과제", "수업", "공부"]):
        context_score += 1
    if topic_context.lower() in user_response.lower():
        context_score += 1

    # Purpose check
    if any(keyword in user_response.lower() for keyword in ["알려줘", "설명해줘", "예시", "풀이", "방법"]):
        purpose_score += 1
    if any(keyword in user_response.lower() for keyword in ["예시", "예시 들어줘", "예를 들어"]):
        purpose_score += 1

    # Convert scores to ratings
    def get_rating(score):
        if score >= 2:
            return "excellent"
        elif score == 1:
            return "good"
        else:
            return "needs_work"

    rubric_result = {
        "specificity": get_rating(specificity_score),
        "context": get_rating(context_score),
        "purpose": get_rating(purpose_score),
        "overall": get_rating(specificity_score + context_score + purpose_score)
    }

    # Generate feedback
    if rubric_result["overall"] == "excellent":
        feedback = "질문이 아주 명확해졌어요! 무엇을, 왜, 어떻게가 모두 잘 드러나 있어요."
        score = 30
    elif rubric_result["overall"] == "good":
        feedback = "좋아졌어요! 질문이 더 명확해졌어요."
        score = 20
    else:
        feedback = "한 부분이 더 명확해지면 좋겠어요."
        score = 10

    return rubric_result, feedback, score

# API functions
def api_session_start(user_id: str = "anonymous") -> Dict[str, Any]:
    session_id = f"session_{st.session_state.session_state['user_progress']['completed_session_count'] + 1}"

    # Select quests (1 intro + 2 main)
    intro_quest = next(item for item in items if item["difficulty"] == "intro")
    main_quests = [item for item in items if item["difficulty"] == "main"][:2]
    quests = [intro_quest] + main_quests

    st.session_state.session_state.update({
        "session_id": session_id,
        "quests": quests,
        "current_quest_index": 0,
        "session_score": 0,
        "answers": []
    })

    return {
        "session_id": session_id,
        "quests": [
            {
                "quest_id": quest["item_id"],
                "quest_type": quest["quiz_type"],
                "difficulty": quest["difficulty"],
                "topic_context": quest["topic_context"],
                "original_question": quest["original_question"],
                "options": quest.get("choices", [])
            }
            for quest in quests
        ],
        "user_progress": st.session_state.session_state["user_progress"]
    }

def api_quest_submit(quest: Dict[str, Any], user_response: Any) -> Dict[str, Any]:
    session_state = st.session_state.session_state
    quest_id = quest["quest_id"]
    quest_type = quest["quest_type"]

    if quest_type == "multiple_choice":
        # Validate response
        if not isinstance(user_response, int) or not 0 <= user_response < len(quest["options"]):
            st.error("선택지를 골라주세요")
            return {"error_code": "E_NO_SELECTION", "error_message": "선택지를 골라주세요"}

        # Get correct answer
        correct_index = quest["choices"].index(answer_key[quest_id])
        is_correct = (user_response == correct_index)

        # Calculate score
        if is_correct:
            earned_score = 20
            feedback = f"정답입니다! {explanations[quest_id]}"
        else:
            earned_score = 5
            feedback = f"이 질문도 좋아요. {explanations[quest_id]}"

        evaluation = {
            "evaluation_type": "correctness",
            "is_correct": is_correct,
            "feedback": feedback
        }
    else:  # question_improvement
        # Validate response
        if not isinstance(user_response, str):
            st.error("질문을 작성해주세요")
            return {"error_code": "E_EMPTY_INPUT", "error_message": "질문을 작성해주세요"}
        if len(user_response.strip()) < 10:
            st.error("조금 더 자세히 작성해주세요 (최소 10자)")
            return {"error_code": "E_TOO_SHORT", "error_message": "조금 더 자세히 작성해주세요 (최소 10자)"}

        # Evaluate response
        rubric_result, feedback, earned_score = evaluate_improvement_question(
            user_response,
            quest["original_question"],
            quest["topic_context"]
        )

        evaluation = {
            "evaluation_type": "rubric",
            "rubric_result": rubric_result,
            "feedback": feedback
        }

    # Update session state
    session_state["session_score"] += earned_score
    session_state["answers"].append({
        "answer_id": f"ans_{len(session_state['answers']) + 1}",
        "session_id": session_state["session_id"],
        "quest_id": quest_id,
        "user_response": user_response,
        "evaluation": evaluation,
        "earned_score": earned_score
    })

    is_session_complete = (session_state["current_quest_index"] + 1) == len(session_state["quests"])

    return {
        "answer_id": f"ans_{len(session_state['answers'])}",
        "evaluation": evaluation,
        "earned_score": earned_score,
        "is_session_complete": is_session_complete
    }

def api_session_result() -> Dict[str, Any]:
    session_state = st.session_state.session_state
    previous_grade = session_state["user_progress"]["current_grade"]

    # Update cumulative score
    session_state["user_progress"]["cumulative_score"] += session_state["session_score"]
    session_state["user_progress"]["completed_session_count"] += 1

    # Determine new grade
    new_grade = determine_grade(session_state["user_progress"]["cumulative_score"])
    session_state["user_progress"]["current_grade"] = new_grade

    grade_up_event = (new_grade != previous_grade)

    return {
        "session_id": session_state["session_id"],
        "session_score": session_state["session_score"],
        "user_progress": session_state["user_progress"],
        "grade_up_event": grade_up_event,
        "previous_grade": previous_grade,
        "new_grade": new_grade
    }

# Main app

def main():
    st.title("📚 질문력 퀘스트")

    if st.session_state.session_state["session_id"] is None:
        # Start screen
        st.markdown("### 오늘의 질문력 퀘스트")
        st.write("3개의 퀘스트를 풀고 질문력 점수를 쌓아보세요!")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("누적 점수", st.session_state.session_state["user_progress"]["cumulative_score"])
        with col2:
            st.metric("현재 등급", st.session_state.session_state["user_progress"]["current_grade"])

        if st.button("세션 시작"):
            api_session_start()
            st.experimental_rerun()
    else:
        session_state = st.session_state.session_state
        current_quest_index = session_state["current_quest_index"]
        quest = session_state["quests"][current_quest_index]

        # Display progress
        st.markdown(f"### 퀘스트 {current_quest_index + 1} / {len(session_state['quests'])}")

        if quest["quiz_type"] == "multiple_choice":
            # Multiple choice quest
            st.markdown(f"#### {quest['title']}")
            st.write(f"학습 맥락: {quest['topic_context']}")
            st.write(f"원본 질문: {quest['original_question']}")
            st.write("이 질문을 더 좋게 바꾼 선택지는 무엇일까요?")

            selected_option = st.radio("", quest["choices"], key=f"option_{current_quest_index}", index=None, help="선택지를 골라주세요")

            if st.button("제출"):
                if selected_option is None:
                    st.error("선택지를 골라주세요")
                else:
                    response = api_quest_submit(quest, quest["choices"].index(selected_option))
                    if "error_code" in response:
                        st.error(response["error_message"])
                    else:
                        st.session_state.session_state["current_quest_index"] += 1
                        st.experimental_rerun()
        else:
            # Question improvement quest
            st.markdown(f"#### {quest['title']}")
            st.write(f"학습 맥락: {quest['topic_context']}")
            st.write(f"원본 질문: {quest['original_question']}")
            st.write("이 질문을 더 명확하게 바꿔보세요. 무엇을, 왜, 어떻게가 들어가면 좋아요.")

            user_response = st.text_area("", key=f"response_{current_quest_index}", height=100)
            st.write(f"{len(user_response)} / 300")

            if st.button("제출"):
                if not user_response.strip():
                    st.error("질문을 작성해주세요")
                elif len(user_response.strip()) < 10:
                    st.error("조금 더 자세히 작성해주세요 (최소 10자)")
                else:
                    response = api_quest_submit(quest, user_response)
                    if "error_code" in response:
                        st.error(response["error_message"])
                    else:
                        st.session_state.session_state["current_quest_index"] += 1
                        st.experimental_rerun()

        # Check if session is complete
        if session_state["current_quest_index"] >= len(session_state["quests"]):
            result = api_session_result()
            st.markdown("### 🎉 오늘의 퀘스트 완료!")
            st.write(f"이번 세션: +{result['session_score']}점")
            st.write(f"전체 누적: {result['user_progress']['cumulative_score']}점")
            st.write(f"현재 등급: {result['user_progress']['current_grade']}")

            if result["grade_up_event"]:
                st.success(f"축하해요! 이제 {result['new_grade']} 단계예요")

            if st.button("새 세션 시작"):
                st.session_state.session_state = {
                    "session_id": None,
                    "quests": [],
                    "current_quest_index": 0,
                    "user_progress": result["user_progress"],
                    "session_score": 0,
                    "answers": []
                }
                st.experimental_rerun()

            if st.button("종료"):
                st.session_state.session_state = {
                    "session_id": None,
                    "quests": [],
                    "current_quest_index": 0,
                    "user_progress": result["user_progress"],
                    "session_score": 0,
                    "answers": []
                }
                st.experimental_rerun()

if __name__ == "__main__":
    main()
