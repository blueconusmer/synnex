import streamlit as st
import json
from pathlib import Path

# Configuration
APP_DIR = Path(__file__).parent
CONTENT_FILENAME = "Question_Quest_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

# Screen constants
SCREEN_START = "start"
SCREEN_MULTIPLE_CHOICE = "multiple_choice"
SCREEN_MULTIPLE_CHOICE_RESULT = "multiple_choice_result"
SCREEN_IMPROVEMENT = "improvement"
SCREEN_IMPROVEMENT_RESULT = "improvement_result"
SCREEN_BATTLE = "battle"
SCREEN_BATTLE_RESULT = "battle_result"
SCREEN_BATTLE_COMPLETED = "battle_completed"
SCREEN_SESSION_RESULT = "session_result"

# Quest sequence
QUEST_SEQUENCE = ["multiple_choice", "situation_card", "question_improvement", "situation_card", "battle"]

# Initialize session state
if "current_screen" not in st.session_state:
    st.session_state.current_screen = SCREEN_START
if "session_data" not in st.session_state:
    st.session_state.session_data = {}
if "current_quest_index" not in st.session_state:
    st.session_state.current_quest_index = 0
if "combo_count" not in st.session_state:
    st.session_state.combo_count = 0
if "session_score" not in st.session_state:
    st.session_state.session_score = 0
if "battle_state" not in st.session_state:
    st.session_state.battle_state = {
        "current_round": 1,
        "user_wins": 0,
        "ai_wins": 0,
        "round_results": [],
        "battle_status": "in_progress",
        "is_perfect": False
    }
if "user_progress" not in st.session_state:
    st.session_state.user_progress = {
        "cumulative_score": 0,
        "current_grade": "bronze",
        "completed_session_count": 0,
        "completed_quest_ids": []
    }

# Load content
def resolve_content_path():
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None


def normalize_correct_option(choices, correct_choice):
    if not isinstance(choices, list):
        choices = []

    if isinstance(correct_choice, int):
        if 0 <= correct_choice < len(choices):
            return correct_choice, choices[correct_choice]
        return -1, ""

    if isinstance(correct_choice, str):
        if correct_choice in choices:
            return choices.index(correct_choice), correct_choice
        return -1, correct_choice

    return -1, ""

content_path = resolve_content_path()
if content_path:
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)
    quests = content.get("items", [])
elif "items" in content:
    quests = content["items"]
else:
    quests = []

# Normalize quest data
normalized_quests = {}
for item in quests:
    quest_id = item.get("item_id")
    if not quest_id:
        continue
    choices = item.get("choices", [])
    correct_option_index, correct_option_text = normalize_correct_option(
        choices,
        item.get("correct_choice"),
    )
    normalized = {
        "quest_id": quest_id,
        "quest_type": item.get("quiz_type"),
        "difficulty": item.get("difficulty"),
        "topic_context": item.get("topic_context"),
        "original_question": item.get("original_question", ""),
        "options": choices,
        "correct_option_index": correct_option_index,
        "correct_option_text": correct_option_text,
        "situation": item.get("situation", ""),
        "ai_question": item.get("ai_question", ""),
        "stage_level": item.get("stage_level", "bronze"),
        "explanation": item.get("explanation", ""),
        "learning_point": item.get("learning_point", ""),
    }
    normalized_quests[quest_id] = normalized

# API functions

def api_session_start():
    # Select quests for this session
    session_quests = []
    for quest_type in QUEST_SEQUENCE:
        for quest_id, quest in normalized_quests.items():
            if quest["quest_type"] == quest_type and quest_id not in st.session_state.user_progress["completed_quest_ids"]:
                session_quests.append(quest_id)
                break
    
    # Initialize session data
    st.session_state.session_data = {
        "session_id": "session_1",
        "quest_sequence": session_quests,
        "session_status": "in_progress",
        "current_quest_index": 0,
        "session_score": 0,
        "combo_count": 0,
        "combo_bonus": 0,
        "battle_state": st.session_state.battle_state.copy()
    }
    st.session_state.current_quest_index = 0
    st.session_state.session_score = 0
    st.session_state.combo_count = 0
    st.session_state.battle_state = {
        "current_round": 1,
        "user_wins": 0,
        "ai_wins": 0,
        "round_results": [],
        "battle_status": "in_progress",
        "is_perfect": False
    }
    st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
    return st.session_state.session_data

def api_quest_submit(quest_id, user_response):
    quest = normalized_quests.get(quest_id)
    if not quest:
        return {"error_code": "E_QUEST_NOT_FOUND", "error_message": "퀘스트를 찾을 수 없습니다"}
    
    if quest["quest_type"] == "multiple_choice":
        # Multiple choice evaluation
        correct_option_index = quest["correct_option_index"]
        is_correct = int(user_response) == correct_option_index
        earned_score = 20 if is_correct else 5
        explanation = quest["explanation"]
        feedback = (
            explanation
            if is_correct
            else f"이 선택도 좋지만 더 나은 답이 있어요. {explanation}"
        )
        
        st.session_state.session_score += earned_score
        return {
            "evaluation": {
                "evaluation_type": "correctness",
                "is_correct": is_correct,
                "feedback": feedback
            },
            "earned_score": earned_score,
            "combo_count": st.session_state.combo_count,
            "is_session_complete": False
        }
    else:
        # Free text evaluation
        situation = quest["situation"]
        original_question = quest["original_question"]
        topic_context = quest["topic_context"]
        
        # Simple rule-based evaluation
        specificity = evaluate_specificity(user_response, topic_context)
        context = evaluate_context(user_response, situation)
        purpose = evaluate_purpose(user_response, original_question if quest["quest_type"] == "question_improvement" else "")
        
        overall = "excellent" if all([s == "excellent" for s in [specificity, context, purpose]]) else \
                 "needs_work" if any([s == "needs_work" for s in [specificity, context, purpose]]) else "good"
        
        rubric_score = sum([2 if s == "excellent" else 1 if s == "good" else 0 for s in [specificity, context, purpose]])
        
        if overall == "excellent":
            earned_score = 30
            feedback = f"아주 명확해졌어요! {get_feedback(specificity, context, purpose)}"
            st.session_state.combo_count += 1
        elif overall == "needs_work":
            earned_score = 10
            feedback = f"한 부분이 더 명확해지면 좋겠어요. {get_feedback(specificity, context, purpose, negative=True)}"
            st.session_state.combo_count = 0
        else:  # good
            earned_score = 20
            feedback = f"좋아졌어요! {get_feedback(specificity, context, purpose)}"
            st.session_state.combo_count += 1
        
        st.session_state.session_score += earned_score
        return {
            "evaluation": {
                "evaluation_type": "rubric",
                "rubric_result": {
                    "specificity": specificity,
                    "context": context,
                    "purpose": purpose,
                    "overall": overall,
                    "rubric_score": rubric_score
                },
                "feedback": feedback
            },
            "earned_score": earned_score,
            "combo_count": st.session_state.combo_count,
            "is_session_complete": False
        }

def api_session_result():
    # Calculate combo bonus
    combo_bonus = 15 if st.session_state.combo_count >= 3 else 10 if st.session_state.combo_count >= 2 else 0
    
    # Update user progress
    st.session_state.user_progress["cumulative_score"] += st.session_state.session_score + combo_bonus
    
    # Determine new grade
    cumulative_score = st.session_state.user_progress["cumulative_score"]
    if cumulative_score >= 600:
        new_grade = "platinum"
    elif cumulative_score >= 300:
        new_grade = "gold"
    elif cumulative_score >= 100:
        new_grade = "silver"
    else:
        new_grade = "bronze"
    
    grade_up_event = new_grade != st.session_state.user_progress["current_grade"]
    st.session_state.user_progress["current_grade"] = new_grade
    st.session_state.user_progress["completed_session_count"] += 1
    
    return {
        "session_id": "session_1",
        "session_score": st.session_state.session_score,
        "combo_bonus": combo_bonus,
        "cumulative_score": st.session_state.user_progress["cumulative_score"],
        "current_grade": new_grade,
        "grade_up_event": grade_up_event
    }

# Evaluation functions

def evaluate_specificity(question, topic_context):
    if any(keyword in question for keyword in topic_context.split()):
        if len(question.split()) > 10:
            return "excellent"
        return "good"
    return "needs_work"

def evaluate_context(question, situation):
    if any(keyword in question for keyword in situation.split()):
        return "excellent"
    return "good" if "왜" in question or "어떻게" in question else "needs_work"

def evaluate_purpose(question, original_question):
    if original_question:
        if "설명" in question or "예시" in question or "방법" in question:
            return "excellent"
        if "알려" in question or "해줘" in question:
            return "good"
        return "needs_work"
    else:
        if "설명" in question or "예시" in question or "방법" in question:
            return "excellent"
        if "알려" in question or "해줘" in question:
            return "good"
        return "needs_work"

def get_feedback(specificity, context, purpose, negative=False):
    feedbacks = []
    if specificity == "excellent":
        feedbacks.append("주제가 명확해요")
    elif negative:
        feedbacks.append("주제를 더 명확히 해주세요")
    
    if context == "excellent":
        feedbacks.append("상황이 잘 드러나요")
    elif negative:
        feedbacks.append("상황을 더 명확히 해주세요")
    
    if purpose == "excellent":
        feedbacks.append("원하는 답이 명확해요")
    elif negative:
        feedbacks.append("원하는 답을 더 명확히 해주세요")
    
    return ", ".join(feedbacks)

# Main app

def main():
    if not content_path:
        st.error(f"콘텐츠 파일을 찾을 수 없습니다. 다음 경로 중 하나에 {CONTENT_FILENAME} 파일이 있어야 합니다:\n- {OUTPUT_PATH}\n- {FALLBACK_OUTPUT_PATH}")
        return
    
    if st.session_state.current_screen == SCREEN_START:
        st.title("📚 Question Quest")
        st.markdown("### 오늘의 질문력 퀘스트")
        st.write(f"현재 등급: {st.session_state.user_progress['current_grade']} 등급")
        st.write(f"누적 점수: {st.session_state.user_progress['cumulative_score']}점")
        st.markdown("---")
        st.markdown("### 세션 구성")
        st.write("Q1 객관식 → Q2 상황카드 → Q3 개선형 → Q4 상황카드 심화 → Q5 배틀 3라운드")
        if st.button("세션 시작"):
            api_session_start()
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE:
        quest_id = st.session_state.session_data["quest_sequence"][st.session_state.current_quest_index]
        quest = normalized_quests.get(quest_id)
        if not quest or quest["quest_type"] != "multiple_choice":
            st.error("객관식 퀘스트를 찾을 수 없습니다")
            return
        
        st.title(f"📚 Question Quest - 퀘스트 {st.session_state.current_quest_index + 1}/5")
        st.markdown(f"### {quest['topic_context']}")
        st.write("다음 중 AI에게 가장 잘 물어본 질문은 무엇일까요?")
        
        selected_option = st.radio("", quest["options"], key="multiple_choice", index=0, disabled=False)
        
        if st.button("제출"):
            # Find selected option index
            selected_index = quest["options"].index(selected_option)
            result = api_quest_submit(quest_id, selected_index)
            st.session_state.session_data["evaluation"] = result.get("evaluation", {})
            st.session_state.session_data["earned_score"] = result.get("earned_score", 0)
            st.session_state.session_data["current_quest_index"] += 1
            st.session_state.current_quest_index += 1
            st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE_RESULT:
        quest_id = st.session_state.session_data["quest_sequence"][st.session_state.current_quest_index - 1]
        quest = normalized_quests.get(quest_id)
        if not quest or quest["quest_type"] != "multiple_choice":
            st.error("객관식 결과 퀘스트를 찾을 수 없습니다")
            return
        
        st.title(f"📚 Question Quest - 퀘스트 {st.session_state.current_quest_index}/5 완료")
        if st.session_state.session_data.get("evaluation", {}).get("is_correct", False):
            st.markdown("### ✅ 정답이에요!")
        else:
            st.markdown("### ⚠️ 이 선택도 좋아요")
        
        st.markdown(f"### 정답: {quest['correct_option_text']}")
        st.markdown(f"### 해설: {quest['explanation']}")
        st.markdown(f"### 획득 점수: +{st.session_state.session_data.get('earned_score', 0)}점")
        
        if st.button("다음 퀘스트로"):
            if st.session_state.current_quest_index < len(QUEST_SEQUENCE) - 1:
                st.session_state.current_screen = SCREEN_IMPROVEMENT
            else:
                st.session_state.current_screen = SCREEN_BATTLE
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT:
        quest_id = st.session_state.session_data["quest_sequence"][st.session_state.current_quest_index]
        quest = normalized_quests.get(quest_id)
        if not quest or quest["quest_type"] not in ["situation_card", "question_improvement"]:
            st.error("작성형 퀘스트를 찾을 수 없습니다")
            return
        
        st.title(f"📚 Question Quest - 퀘스트 {st.session_state.current_quest_index + 1}/5")
        st.markdown(f"### {quest['topic_context']}")
        
        if quest["quest_type"] == "situation_card":
            st.markdown(f"#### 상황: {quest['situation']}")
            st.write("이 상황에서 AI에게 어떻게 질문하시겠습니까? 주제·상황·원하는 답을 넣어보세요.")
        else:  # question_improvement
            st.markdown(f"#### 원본 질문: {quest['original_question']}")
            st.write("위 질문을 더 구체적이고 목적성 있는 질문으로 바꿔보세요.")
        
        user_response = st.text_area("질문 입력", value="", key="question_input", max_chars=300, help="최소 10자 이상 입력해주세요")
        
        if st.button("제출"):
            if len(user_response.strip()) < 10:
                st.warning("질문을 10자 이상 입력해주세요")
            else:
                result = api_quest_submit(quest_id, user_response)
                st.session_state.session_data["evaluation"] = result.get("evaluation", {})
                st.session_state.session_data["earned_score"] = result.get("earned_score", 0)
                st.session_state.session_data["current_quest_index"] += 1
                st.session_state.current_quest_index += 1
                st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT_RESULT:
        quest_id = st.session_state.session_data["quest_sequence"][st.session_state.current_quest_index - 1]
        quest = normalized_quests.get(quest_id)
        if not quest or quest["quest_type"] not in ["situation_card", "question_improvement"]:
            st.error("작성형 결과 퀘스트를 찾을 수 없습니다")
            return
        
        evaluation = st.session_state.session_data.get("evaluation", {})
        rubric_result = evaluation.get("rubric_result", {})
        overall = rubric_result.get("overall", "")
        
        st.title(f"📚 Question Quest - 퀘스트 {st.session_state.current_quest_index}/5 완료")
        
        if overall == "excellent":
            st.markdown("### ✅ 아주 명확해졌어요!")
        elif overall == "needs_work":
            st.markdown("### ⚠️ 한 부분이 더 명확해지면 좋겠어요")
        else:  # good
            st.markdown("### 🟡 좋아졌어요!")
        
        st.markdown(f"### 루브릭 결과:")
        st.markdown(f"- 구체성: {rubric_result.get('specificity', '')}")
        st.markdown(f"- 맥락성: {rubric_result.get('context', '')}")
        st.markdown(f"- 목적성: {rubric_result.get('purpose', '')}")
        st.markdown(f"### 피드백: {evaluation.get('feedback', '')}")
        st.markdown(f"### 획득 점수: +{st.session_state.session_data.get('earned_score', 0)}점")
        
        if st.session_state.combo_count >= 2:
            st.markdown(f"### 🔥 {st.session_state.combo_count}콤보!")
        
        if st.session_state.current_quest_index < len(QUEST_SEQUENCE) - 1:
            if st.button("다음 퀘스트로"):
                st.session_state.current_screen = SCREEN_IMPROVEMENT
                st.rerun()
        else:
            if st.button("배틀 시작!"):
                st.session_state.current_screen = SCREEN_BATTLE
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_BATTLE:
        quest_id = st.session_state.session_data["quest_sequence"][st.session_state.current_quest_index]
        quest = normalized_quests.get(quest_id)
        if not quest or quest["quest_type"] != "battle":
            st.error("배틀 퀘스트를 찾을 수 없습니다")
            return
        
        battle_state = st.session_state.battle_state
        current_round = battle_state["current_round"]
        
        st.title(f"📚 Question Quest - 배틀 라운드 {current_round}/3")
        st.markdown(f"### 승리 현황: 나 {battle_state['user_wins']}승 vs AI {battle_state['ai_wins']}승")
        
        # Get situation for this round
        situation = f"라운드 {current_round} 상황: {quest['situation']}" if current_round == 1 else \
                  f"라운드 {current_round} 상황: 추가 상황 설명 {current_round}"
        
        st.markdown(f"#### {situation}")
        st.write("AI보다 더 좋은 질문을 작성해보세요!")
        
        user_response = st.text_area("질문 입력", value="", key=f"battle_input_{current_round}", max_chars=300, help="최소 10자 이상 입력해주세요")
        
        if st.button("제출"):
            if len(user_response.strip()) < 10:
                st.warning("질문을 10자 이상 입력해주세요")
            else:
                # Simple battle evaluation
                ai_question = quest["ai_question"]
                
                # Evaluate both questions
                situation_eval = quest["situation"]
                
                user_specificity = evaluate_specificity(user_response, quest["topic_context"])
                user_context = evaluate_context(user_response, situation_eval)
                user_purpose = evaluate_purpose(user_response, "")
                
                ai_specificity = evaluate_specificity(ai_question, quest["topic_context"])
                ai_context = evaluate_context(ai_question, situation_eval)
                ai_purpose = evaluate_purpose(ai_question, "")
                
                user_score = sum([2 if s == "excellent" else 1 if s == "good" else 0 for s in [user_specificity, user_context, user_purpose]])
                ai_score = sum([2 if s == "excellent" else 1 if s == "good" else 0 for s in [ai_specificity, ai_context, ai_purpose]])
                
                round_winner = "user" if user_score > ai_score else "ai"
                earned_score = 20 if round_winner == "user" else 5
                
                # Update battle state
                if round_winner == "user":
                    battle_state["user_wins"] += 1
                    st.session_state.combo_count += 1
                else:
                    battle_state["ai_wins"] += 1
                    st.session_state.combo_count = 0
                
                battle_state["round_results"].append({
                    "round_number": current_round,
                    "user_question": user_response,
                    "ai_question": ai_question,
                    "user_rubric": {
                        "specificity": user_specificity,
                        "context": user_context,
                        "purpose": user_purpose,
                        "rubric_score": user_score
                    },
                    "ai_rubric": {
                        "specificity": ai_specificity,
                        "context": ai_context,
                        "purpose": ai_purpose,
                        "rubric_score": ai_score
                    },
                    "round_winner": round_winner,
                    "earned_score": earned_score
                })
                
                st.session_state.session_score += earned_score
                
                # Check if battle should continue
                if battle_state["user_wins"] >= 2 or battle_state["ai_wins"] >= 2 or current_round == 3:
                    battle_state["battle_status"] = "user_won" if battle_state["user_wins"] >= 2 else "ai_won"
                    battle_state["is_perfect"] = battle_state["user_wins"] == 3
                    st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
                else:
                    battle_state["current_round"] += 1
                    st.session_state.current_screen = SCREEN_BATTLE_RESULT
                
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_BATTLE_RESULT:
        battle_state = st.session_state.battle_state
        current_round = battle_state["current_round"] - 1  # Last completed round
        round_result = battle_state["round_results"][current_round - 1] if current_round > 0 else {}
        
        st.title(f"📚 Question Quest - 배틀 라운드 {current_round}/3 결과")
        
        if round_result.get("round_winner") == "user":
            st.markdown("### ✅ 이겼어요!")
        else:
            st.markdown("### ⚠️ 이번엔 AI가 더 잘했어요")
        
        st.markdown(f"### 비교 표:")
        st.markdown(f"- **내 질문**: {round_result.get('user_question', '')}")
        st.markdown(f"- **AI 질문**: {round_result.get('ai_question', '')}")
        st.markdown(f"- **내 질문 평가**: {round_result.get('user_rubric', {}).get('rubric_score', 0)}점")
        st.markdown(f"- **AI 질문 평가**: {round_result.get('ai_rubric', {}).get('rubric_score', 0)}점")
        st.markdown(f"### 획득 점수: +{round_result.get('earned_score', 0)}점")
        st.markdown(f"### 승리 현황: 나 {battle_state['user_wins']}승 vs AI {battle_state['ai_wins']}승")
        
        if battle_state["user_wins"] < 2 and battle_state["ai_wins"] < 2 and current_round < 3:
            if st.button("다음 라운드"):
                st.session_state.current_screen = SCREEN_BATTLE
                st.rerun()
        else:
            if st.button("최종 결과 보기"):
                st.session_state.current_screen = SCREEN_BATTLE_COMPLETED
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_BATTLE_COMPLETED:
        battle_state = st.session_state.battle_state
        
        st.title("📚 Question Quest - 배틀 최종 결과")
        
        if battle_state["battle_status"] == "user_won":
            st.markdown("### ✅ AI를 이겼어요!")
            if battle_state["is_perfect"]:
                st.markdown("#### 퍼펙트 클리어!")
        else:
            st.markdown("### ⚠️ 다음엔 이길 수 있어요!")
        
        st.markdown(f"### 최종 스코어: {battle_state['user_wins']}승 vs {battle_state['ai_wins']}승")
        st.markdown(f"### 배틀 보너스: +{15 if battle_state['is_perfect'] else 0}점")
        
        if st.button("세션 결과 보기"):
            st.session_state.current_screen = SCREEN_SESSION_RESULT
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_SESSION_RESULT:
        result = api_session_result()
        
        st.title("📚 Question Quest - 세션 완료!")
        st.markdown(f"### 이번 세션 획득 점수: {result['session_score']}점")
        
        if result['combo_bonus'] > 0:
            st.markdown(f"### 콤보 보너스: +{result['combo_bonus']}점")
        
        st.markdown(f"### 누적 총점: {result['cumulative_score']}점")
        st.markdown(f"### 현재 등급: {result['current_grade']} 등급")
        
        if result['grade_up_event']:
            st.markdown(f"#### 축하해요! 이제 {result['current_grade']} 단계예요!")
        
        if st.button("새 세션 시작"):
            # Reset session state
            st.session_state.current_screen = SCREEN_START
            st.session_state.session_data = {}
            st.session_state.current_quest_index = 0
            st.session_state.combo_count = 0
            st.session_state.session_score = 0
            st.session_state.battle_state = {
                "current_round": 1,
                "user_wins": 0,
                "ai_wins": 0,
                "round_results": [],
                "battle_status": "in_progress",
                "is_perfect": False
            }
            st.rerun()

if __name__ == "__main__":
    main()
