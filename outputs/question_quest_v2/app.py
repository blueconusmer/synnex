import streamlit as st
import json
import os
from pathlib import Path

# Configuration
APP_DIR = Path(__file__).parent
CONTENT_FILENAME = "260429_퀘스트_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

# Screen constants
SCREEN_START = "session_start"
SCREEN_MULTIPLE_CHOICE = "quest_active"
SCREEN_MULTIPLE_CHOICE_RESULT = "quest_feedback"
SCREEN_IMPROVEMENT = "quest_active"
SCREEN_IMPROVEMENT_RESULT = "quest_feedback"
SCREEN_BATTLE = "battle_round_active"
SCREEN_BATTLE_RESULT = "battle_round_feedback"
SCREEN_BATTLE_COMPLETED = "battle_completed"
SCREEN_SESSION_RESULT = "session_completed"

# Initialize session state
if "current_screen" not in st.session_state:
    st.session_state.current_screen = SCREEN_START
if "session" not in st.session_state:
    st.session_state.session = {
        "session_id": "temp_session",
        "user_id": "temp_user",
        "quest_sequence": [],
        "session_status": "in_progress",
        "current_quest_index": 0,
        "session_score": 0,
        "combo_count": 0,
        "combo_bonus": 0,
        "battle_state": {
            "current_round": 1,
            "user_wins": 0,
            "ai_wins": 0,
            "round_results": [],
            "battle_status": "in_progress",
            "is_perfect": False
        },
        "started_at": "2023-01-01T00:00:00Z",
        "completed_at": None
    }
if "user_progress" not in st.session_state:
    st.session_state.user_progress = {
        "user_id": "temp_user",
        "cumulative_score": 0,
        "current_grade": "bronze",
        "completed_session_count": 0,
        "completed_quest_ids": []
    }
if "content" not in st.session_state:
    st.session_state.content = load_content()


def resolve_content_path():
    """Find the first existing content file path"""
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None


def load_content():
    """Load content JSON from resolved path"""
    content_path = resolve_content_path()
    if not content_path:
        st.warning(f"콘텐츠 파일을 찾을 수 없습니다. 다음 위치에 파일을 배치해주세요: {', '.join(str(p) for p in CONTENT_CANDIDATE_PATHS)}")
        return {"items": []}
    
    try:
        with open(content_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"콘텐츠 파일을 읽는 중 오류가 발생했습니다: {e}")
        return {"items": []}


def normalize_quest(item):
    """Normalize raw content item to quest format"""
    quest = {
        "quest_id": item.get("item_id", ""),
        "quest_type": item.get("quiz_type", ""),
        "difficulty": item.get("difficulty", ""),
        "topic_context": item.get("topic_context", ""),
        "original_question": item.get("original_question", ""),
        "options": item.get("choices", []),
        "correct_option_index": item.get("correct_choice", "") if item.get("correct_choice", "") is not None else None,
        "correct_option_text": item.get("correct_choice", "") if item.get("choices", []) else "",
        "situation": item.get("situation", ""),
        "ai_question": item.get("ai_question", ""),
        "explanation": item.get("explanation", ""),
        "learning_point": item.get("learning_point", "")
    }
    
    # Handle correct option text
    if quest["correct_option_index"] is not None and isinstance(quest["correct_option_index"], int):
        if 0 <= quest["correct_option_index"] < len(quest["options"]):
            quest["correct_option_text"] = quest["options"][quest["correct_option_index"]]
        else:
            quest["correct_option_text"] = ""
    
    return quest


def get_current_quest():
    """Get current quest from session state"""
    if not st.session_state.session["quest_sequence"]:
        return None
    
    quest_id = st.session_state.session["quest_sequence"][st.session_state.session["current_quest_index"]]
    for item in st.session_state.content.get("items", []):
        if item.get("item_id") == quest_id:
            return normalize_quest(item)
    return None


def api_session_start():
    """Simulate session start API call"""
    # In real app this would call backend API
    # Here we simulate by selecting quests from content
    
    quest_types = ["multiple_choice", "situation_card", "question_improvement", "situation_card", "battle"]
    quest_sequence = []
    
    # Select one quest of each type
    for quest_type in quest_types:
        for item in st.session_state.content.get("items", []):
            if item.get("quiz_type") == quest_type and item.get("item_id") not in st.session_state.session["completed_quest_ids"]:
                quest_sequence.append(item.get("item_id"))
                break
    
    st.session_state.session["quest_sequence"] = quest_sequence
    st.session_state.session["current_quest_index"] = 0
    st.session_state.session["session_score"] = 0
    st.session_state.session["combo_count"] = 0
    st.session_state.session["combo_bonus"] = 0
    st.session_state.session["battle_state"] = {
        "current_round": 1,
        "user_wins": 0,
        "ai_wins": 0,
        "round_results": [],
        "battle_status": "in_progress",
        "is_perfect": False
    }
    st.session_state.session["session_status"] = "in_progress"
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
    st.rerun()


def evaluate_multiple_choice(selected_index):
    """Evaluate multiple choice answer"""
    quest = get_current_quest()
    if not quest or quest["quest_type"] != "multiple_choice":
        return None
    
    is_correct = (selected_index == quest["correct_option_index"])
    earned_score = 20 if is_correct else 5
    
    feedback = {
        "evaluation": {
            "evaluation_type": "correctness",
            "is_correct": is_correct,
            "feedback": quest["explanation"]
        },
        "earned_score": earned_score,
        "combo_count": 0,
        "is_session_complete": False
    }
    
    # Update session
    st.session_state.session["session_score"] += earned_score
    st.session_state.session["completed_quest_ids"].append(quest["quest_id"])
    
    return feedback


def evaluate_improvement_question(user_response, original_question, topic_context):
    """Evaluate improvement question using simple heuristics"""
    # In real app this would use LLM evaluation
    # Here we use simple heuristics based on content keywords
    
    score = 0
    
    # Check if user response contains topic context
    if topic_context.lower() in user_response.lower():
        score += 2
    
    # Check if user response contains situation context
    quest = get_current_quest()
    if quest and "situation" in quest and quest["situation"]:
        if quest["situation"].lower() in user_response.lower():
            score += 2
    
    # Check if user response contains desired answer form
    if "원하는 답의 형태" in user_response:
        score += 2
    
    # Determine rubric result
    if score >= 6:
        rubric_result = {
            "specificity": "excellent",
            "context": "excellent",
            "purpose": "excellent",
            "overall": "excellent",
            "rubric_score": 6
        }
        feedback = "아주 명확해졌어요! 무엇을, 왜, 어떻게 모두 잘 담겨 있어요."
        earned_score = 30
        combo_increase = 1
    elif score >= 3:
        rubric_result = {
            "specificity": "good",
            "context": "good",
            "purpose": "good",
            "overall": "good",
            "rubric_score": 3
        }
        feedback = "좋아졌어요! 무엇을, 왜, 어떻게 중 일부가 명확해졌어요."
        earned_score = 20
        combo_increase = 1
    else:
        rubric_result = {
            "specificity": "needs_work",
            "context": "needs_work",
            "purpose": "needs_work",
            "overall": "needs_work",
            "rubric_score": 0
        }
        feedback = "한 부분이 더 명확해지면 좋겠어요. 무엇을, 왜, 어떻게를 모두 넣어보세요."
        earned_score = 10
        combo_increase = -st.session_state.session["combo_count"]
    
    # Update combo count
    new_combo = max(0, st.session_state.session["combo_count"] + combo_increase)
    st.session_state.session["combo_count"] = new_combo
    
    # Update session score
    st.session_state.session["session_score"] += earned_score
    st.session_state.session["completed_quest_ids"].append(quest["quest_id"])
    
    return {
        "evaluation": {
            "evaluation_type": "rubric",
            "rubric_result": rubric_result,
            "feedback": feedback
        },
        "earned_score": earned_score,
        "combo_count": new_combo,
        "is_session_complete": False
    }


def evaluate_battle_round(user_question, ai_question, situation):
    """Evaluate battle round using simple heuristics"""
    # In real app this would use LLM comparison
    # Here we use simple heuristics based on content keywords
    
    user_score = 0
    ai_score = 0
    
    # Check if contains topic context
    quest = get_current_quest()
    if quest and "topic_context" in quest and quest["topic_context"]:
        if quest["topic_context"].lower() in user_question.lower():
            user_score += 2
        if quest["topic_context"].lower() in ai_question.lower():
            ai_score += 2
    
    # Check if contains situation
    if situation.lower() in user_question.lower():
        user_score += 2
    if situation.lower() in ai_question.lower():
        ai_score += 2
    
    # Check if contains desired answer form
    if "원하는 답의 형태" in user_question:
        user_score += 2
    if "원하는 답의 형태" in ai_question:
        ai_score += 2
    
    # Determine winner
    round_winner = "user" if user_score > ai_score else "ai"
    earned_score = 20 if round_winner == "user" else 5
    
    # Update battle state
    battle_state = st.session_state.session["battle_state"]
    if round_winner == "user":
        battle_state["user_wins"] += 1
        battle_state["combo_count"] = battle_state.get("combo_count", 0) + 1
    else:
        battle_state["ai_wins"] += 1
        battle_state["combo_count"] = 0
    
    battle_state["current_round"] += 1
    
    # Check if battle is completed
    is_battle_completed = (battle_state["user_wins"] >= 2 or battle_state["ai_wins"] >= 2 or battle_state["current_round"] > 3)
    
    return {
        "round_result": {
            "round_number": battle_state["current_round"] - 1,
            "user_question": user_question,
            "ai_question": ai_question,
            "user_rubric": {
                "specificity": "excellent" if user_score >= 6 else "good" if user_score >= 3 else "needs_work",
                "context": "excellent" if user_score >= 6 else "good" if user_score >= 3 else "needs_work",
                "purpose": "excellent" if user_score >= 6 else "good" if user_score >= 3 else "needs_work",
                "overall": "excellent" if user_score >= 6 else "good" if user_score >= 3 else "needs_work",
                "rubric_score": user_score
            },
            "ai_rubric": {
                "specificity": "excellent" if ai_score >= 6 else "good" if ai_score >= 3 else "needs_work",
                "context": "excellent" if ai_score >= 6 else "good" if ai_score >= 3 else "needs_work",
                "purpose": "excellent" if ai_score >= 6 else "good" if ai_score >= 3 else "needs_work",
                "overall": "excellent" if ai_score >= 6 else "good" if ai_score >= 3 else "needs_work",
                "rubric_score": ai_score
            },
            "round_winner": round_winner,
            "earned_score": earned_score
        },
        "battle_state": battle_state,
        "is_battle_completed": is_battle_completed
    }


def api_quest_submit(user_response):
    """Simulate quest submit API call"""
    quest = get_current_quest()
    if not quest:
        return None
    
    if quest["quest_type"] == "multiple_choice":
        # For multiple choice, user_response should be index
        try:
            selected_index = int(user_response)
            return evaluate_multiple_choice(selected_index)
        except:
            return None
    elif quest["quest_type"] in ["situation_card", "question_improvement"]:
        # For improvement questions
        return evaluate_improvement_question(
            user_response,
            quest.get("original_question", ""),
            quest.get("topic_context", "")
        )
    elif quest["quest_type"] == "battle":
        # For battle rounds
        battle_state = st.session_state.session["battle_state"]
        situation = quest.get("situation", "")
        ai_question = quest.get("ai_question", "")
        
        result = evaluate_battle_round(
            user_response,
            ai_question,
            situation
        )
        
        # Update session score
        st.session_state.session["session_score"] += result["round_result"]["earned_score"]
        
        return result
    
    return None


def api_session_result():
    """Simulate session result API call"""
    # In real app this would call backend API
    # Here we just return session data
    
    session = st.session_state.session
    user_progress = st.session_state.user_progress
    
    # Calculate combo bonus
    combo_bonus = 0
    if session["combo_count"] >= 3:
        combo_bonus = 15
    elif session["combo_count"] >= 2:
        combo_bonus = 10
    
    # Calculate battle bonus
    battle_bonus = 0
    if session["battle_state"]["user_wins"] >= 2:
        battle_bonus = 20
        if session["battle_state"]["is_perfect"]:
            battle_bonus += 15
    
    # Update user progress
    total_score = session["session_score"] + combo_bonus + battle_bonus
    user_progress["cumulative_score"] += total_score
    user_progress["completed_session_count"] += 1
    
    # Determine grade
    if user_progress["cumulative_score"] >= 600:
        user_progress["current_grade"] = "platinum"
    elif user_progress["cumulative_score"] >= 300:
        user_progress["current_grade"] = "gold"
    elif user_progress["cumulative_score"] >= 100:
        user_progress["current_grade"] = "silver"
    else:
        user_progress["current_grade"] = "bronze"
    
    return {
        "session_id": session["session_id"],
        "session_score": session["session_score"],
        "combo_bonus": combo_bonus,
        "battle_bonus": battle_bonus,
        "user_progress": user_progress
    }

# Main app

def main():
    """Main application"""
    st.session_state.content = load_content()
    
    if st.session_state.current_screen == SCREEN_START:
        render_start_screen()
    elif st.session_state.current_screen in [SCREEN_MULTIPLE_CHOICE, SCREEN_IMPROVEMENT, SCREEN_BATTLE]:
        render_quest_screen()
    elif st.session_state.current_screen in [SCREEN_MULTIPLE_CHOICE_RESULT, SCREEN_IMPROVEMENT_RESULT, SCREEN_BATTLE_RESULT]:
        render_quest_result_screen()
    elif st.session_state.current_screen == SCREEN_BATTLE_COMPLETED:
        render_battle_completed_screen()
    elif st.session_state.current_screen == SCREEN_SESSION_RESULT:
        render_session_result_screen()


def render_start_screen():
    """Render start screen"""
    st.title("📚 질문력 퀘스트")
    st.markdown("### AI에게 잘 질문하는 법을 게임처럼 배워보세요!")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("누적 점수", st.session_state.user_progress["cumulative_score"])
    with col2:
        st.metric("현재 등급", st.session_state.user_progress["current_grade"])
    
    st.markdown("#### 퀘스트 진행 순서")
    st.write("Q1 객관식 → Q2 상황카드 → Q3 개선형 → Q4 상황카드 심화 → Q5 배틀 3라운드")
    
    if st.button("세션 시작"):
        api_session_start()


def render_quest_screen():
    """Render quest screen"""
    quest = get_current_quest()
    if not quest:
        st.error("퀘스트를 불러올 수 없습니다")
        return
    
    st.title(f"📚 퀘스트 {st.session_state.session['current_quest_index'] + 1} / 5")
    st.markdown(f"### {quest['topic_context']}")
    
    if quest["quest_type"] == "multiple_choice":
        render_multiple_choice(quest)
    elif quest["quest_type"] in ["situation_card", "question_improvement"]:
        render_improvement_quest(quest)
    elif quest["quest_type"] == "battle":
        render_battle_quest(quest)


def render_multiple_choice(quest):
    """Render multiple choice quest"""
    st.markdown("#### 다음 중 가장 좋은 질문은?")
    st.write(quest.get("original_question", ""))
    
    selected_index = st.radio("", quest["options"], index=None, key="multiple_choice_selection")
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("제출"):
            if selected_index is not None:
                feedback = api_quest_submit(selected_index)
                if feedback:
                    st.session_state.quest_feedback = feedback
                    st.session_state.current_quest_index = st.session_state.session["current_quest_index"]
                    st.session_state.session["current_quest_index"] += 1
                    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
                    st.rerun()
            else:
                st.error("선택지를 골라주세요")


def render_improvement_quest(quest):
    """Render improvement quest"""
    if quest["quest_type"] == "situation_card":
        st.markdown("#### 다음 상황에서 AI에게 어떻게 질문하시겠어요?")
        st.write(quest.get("situation", ""))
    else:  # question_improvement
        st.markdown("#### 다음 질문을 더 구체적으로 개선해보세요")
        st.write(quest.get("original_question", ""))
    
    user_response = st.text_area("질문 입력", value="", key="improvement_input", height=100)
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("제출"):
            if len(user_response.strip()) < 10:
                st.error("조금 더 자세히 작성해주세요 (최소 10자)")
            else:
                feedback = api_quest_submit(user_response)
                if feedback:
                    st.session_state.quest_feedback = feedback
                    st.session_state.session["current_quest_index"] += 1
                    st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
                    st.rerun()


def render_battle_quest(quest):
    """Render battle quest"""
    battle_state = st.session_state.session["battle_state"]
    
    st.markdown(f"#### 배틀 라운드 {battle_state['current_round']} / 3")
    st.markdown("#### 다음 상황에서 AI보다 더 좋은 질문을 만들어보세요")
    st.write(quest.get("situation", ""))
    
    user_response = st.text_area("질문 입력", value="", key="battle_input", height=100)
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("제출"):
            if len(user_response.strip()) < 10:
                st.error("조금 더 자세히 작성해주세요 (최소 10자)")
            else:
                result = api_quest_submit(user_response)
                if result:
                    st.session_state.battle_result = result
                    if result["is_battle_completed"]:
                        st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
                    else:
                        st.session_state.current_screen = SCREEN_BATTLE_RESULT
                    st.rerun()


def render_quest_result_screen():
    """Render quest result screen"""
    feedback = getattr(st.session_state, "quest_feedback", None)
    if not feedback:
        st.error("피드백을 불러올 수 없습니다")
        return
    
    st.title("✅ 결과 확인")
    
    if feedback["evaluation"]["evaluation_type"] == "correctness":
        if feedback["evaluation"]["is_correct"]:
            st.markdown("#### 정답이에요!")
        else:
            st.markdown("#### 이 선택도 좋아요")
        
        st.write(f"획득 점수: +{feedback['earned_score']}점")
        st.write("해설:")
        st.write(feedback["evaluation"]["feedback"])
    else:  # rubric
        rubric = feedback["evaluation"]["rubric_result"]
        st.markdown(f"#### {rubric['overall'].capitalize()}")
        
        st.write(f"획득 점수: +{feedback['earned_score']}점")
        st.write("루브릭 평가:")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("구체성", rubric["specificity"])
        with col2:
            st.metric("맥락성", rubric["context"])
        with col3:
            st.metric("목적성", rubric["purpose"])
        
        st.write("피드백:")
        st.write(feedback["evaluation"]["feedback"])
    
    if feedback["combo_count"] >= 2:
        st.markdown(f"🔥 {feedback['combo_count']}콤보!")
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("다음"):
            if st.session_state.session["current_quest_index"] < len(st.session_state.session["quest_sequence"]):
                if st.session_state.session["quest_sequence"][st.session_state.session["current_quest_index"]] == "battle":
                    st.session_state.current_screen = SCREEN_BATTLE
                else:
                    st.session_state.current_screen = SCREEN_IMPROVEMENT
            else:
                st.session_state.current_screen = SCREEN_SESSION_RESULT
            st.rerun()


def render_battle_result_screen():
    """Render battle result screen"""
    result = getattr(st.session_state, "battle_result", None)
    if not result:
        st.error("배틀 결과를 불러올 수 없습니다")
        return
    
    st.title("✅ 배틀 결과")
    
    round_result = result["round_result"]
    
    if round_result["round_winner"] == "user":
        st.markdown("#### 이겼어요!")
    else:
        st.markdown("#### 이번엔 AI가 더 잘했어요")
    
    st.write(f"획득 점수: +{round_result['earned_score']}점")
    st.write("비교 표:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 내 질문")
        st.write(round_result["user_question"])
        st.markdown(f"- 구체성: {round_result['user_rubric']['specificity']}")
        st.markdown(f"- 맥락성: {round_result['user_rubric']['context']}")
        st.markdown(f"- 목적성: {round_result['user_rubric']['purpose']}")
        st.markdown(f"- 합산: {round_result['user_rubric']['rubric_score']}")
    with col2:
        st.markdown("#### AI 질문")
        st.write(round_result["ai_question"])
        st.markdown(f"- 구체성: {round_result['ai_rubric']['specificity']}")
        st.markdown(f"- 맥락성: {round_result['ai_rubric']['context']}")
        st.markdown(f"- 목적성: {round_result['ai_rubric']['purpose']}")
        st.markdown(f"- 합산: {round_result['ai_rubric']['rubric_score']}")
    
    battle_state = result["battle_state"]
    st.write(f"승패 현황: 나 {battle_state['user_wins']}승 vs AI {battle_state['ai_wins']}승")
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("다음 라운드"):
            if result["is_battle_completed"]:
                st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
            else:
                st.session_state.current_screen = SCREEN_BATTLE
            st.rerun()


def render_battle_completed_screen():
    """Render battle completed screen"""
    battle_state = st.session_state.session["battle_state"]
    
    st.title("🏆 배틀 최종 결과")
    
    if battle_state["user_wins"] >= 2:
        st.markdown("#### AI를 이겼어요!")
        if battle_state["is_perfect"]:
            st.markdown("퍼펙트 클리어!")
    else:
        st.markdown("#### 다음엔 이길 수 있어요!")
    
    st.write(f"최종 스코어: 나 {battle_state['user_wins']}승 vs AI {battle_state['ai_wins']}승")
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("결과 보기"):
            st.session_state.current_screen = SCREEN_SESSION_RESULT
            st.rerun()


def render_session_result_screen():
    """Render session result screen"""
    result = api_session_result()
    
    st.title("🏆 세션 완료!")
    st.markdown(f"#### 이번 세션 획득 점수: {result['session_score']}점")
    
    if result['combo_bonus'] > 0:
        st.markdown(f"콤보 보너스: +{result['combo_bonus']}점")
    
    if result['battle_bonus'] > 0:
        st.markdown(f"배틀 보너스: +{result['battle_bonus']}점")
    
    st.markdown(f"#### 누적 총점: {result['user_progress']['cumulative_score']}점")
    st.markdown(f"#### 현재 등급: {result['user_progress']['current_grade']} 등급")
    
    if hasattr(st.session_state, "prev_grade") and st.session_state.prev_grade != result['user_progress']['current_grade']:
        st.markdown(f"축하해요! 이제 {result['user_progress']['current_grade']} 단계예요!")
    
    col1, col2 = st.columns(2)
    with col2:
        if st.button("새 세션 시작"):
            st.session_state.current_screen = SCREEN_START
            st.session_state.session = {
                "session_id": "temp_session",
                "user_id": "temp_user",
                "quest_sequence": [],
                "session_status": "in_progress",
                "current_quest_index": 0,
                "session_score": 0,
                "combo_count": 0,
                "combo_bonus": 0,
                "battle_state": {
                    "current_round": 1,
                    "user_wins": 0,
                    "ai_wins": 0,
                    "round_results": [],
                    "battle_status": "in_progress",
                    "is_perfect": False
                },
                "started_at": "2023-01-01T00:00:00Z",
                "completed_at": None
            }
            st.rerun()

if __name__ == "__main__":
    main()
