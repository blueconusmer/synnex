import streamlit as st
import json
import os
from pathlib import Path

APP_DIR = Path(__file__).parent
CONTENT_FILENAME = "Question_Coaching_Chatbot_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

# 화면 상태 상수 정의
SCREEN_START = "start"
SCREEN_MULTIPLE_CHOICE = "multiple_choice"
SCREEN_MULTIPLE_CHOICE_RESULT = "multiple_choice_result"
SCREEN_IMPROVEMENT = "improvement"
SCREEN_IMPROVEMENT_RESULT = "improvement_result"
SCREEN_SESSION_RESULT = "session_result"

# 콘텐츠 파일 경로 확인 함수
def resolve_content_path() -> Path | None:
    for candidate in CONTENT_CANDIDATE_PATHS:
        if candidate.exists():
            return candidate
    return None

# 콘텐츠 로드 함수
def load_content(content_path: Path) -> dict:
    with open(content_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 초기 상태 설정
def initialize_session_state():
    if "current_screen" not in st.session_state:
        st.session_state.current_screen = SCREEN_START
    if "user_question" not in st.session_state:
        st.session_state.user_question = ""
    if "improved_question" not in st.session_state:
        st.session_state.improved_question = ""
    if "current_step" not in st.session_state:
        st.session_state.current_step = 0
    if "feedback_messages" not in st.session_state:
        st.session_state.feedback_messages = []
    if "session_data" not in st.session_state:
        st.session_state.session_data = {}

# API 함수들
def api_session_start():
    st.session_state.session_data = {
        "quests": [],
        "results": {}
    }
    return st.session_state.session_data

def api_quest_submit(quest_id: str, user_answer: str) -> dict:
    session_data = st.session_state.session_data
    session_data["quests"].append({
        "quest_id": quest_id,
        "user_answer": user_answer
    })
    # 간단한 평가 로직
    correct = False
    feedback = ""
    for quest in content.get("quests", []):
        if quest["quest_id"] == quest_id:
            if quest["correct_option_text"] == user_answer:
                correct = True
                feedback = "정답입니다!"
            else:
                feedback = f"틀렸습니다. 정답은 {quest["correct_option_text"]}입니다."
            break
    
    session_data["results"][quest_id] = {
        "correct": correct,
        "feedback": feedback
    }
    return session_data["results"][quest_id]

def api_session_result() -> dict:
    return st.session_state.session_data

# 메인 앱
def main():
    content_path = resolve_content_path()
    if not content_path:
        st.warning(f"콘텐츠 파일을 찾을 수 없습니다. 다음 위치에 파일이 있는지 확인하세요: {', '.join(str(p) for p in CONTENT_CANDIDATE_PATHS)}")
        return
    
    global content
    content = load_content(content_path)
    initialize_session_state()
    
    if st.session_state.current_screen == SCREEN_START:
        st.title("질문 코칭 챗봇")
        st.write("질문을 입력하면 AI가 질문을 더 명확하게 만들 수 있도록 도와줄 거예요!")
        st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
        st.rerun()
    
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE:
        st.header("질문 선택")
        quests = content.get("quests", [])
        if not quests:
            st.warning("사용 가능한 질문이 없습니다.")
            return
        
        selected_quest = st.selectbox("질문을 선택하세요", [q["quest_id"] for q in quests])
        quest = next((q for q in quests if q["quest_id"] == selected_quest), None)
        
        if quest:
            st.write(f"### {quest.get('question_text', '질문 내용이 없습니다.')}")
            options = quest.get("options", [])
            user_answer = st.selectbox("답을 선택하세요", options)
            
            if st.button("제출"):
                result = api_quest_submit(selected_quest, user_answer)
                st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT
                st.session_state.last_result = result
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_MULTIPLE_CHOICE_RESULT:
        st.header("결과")
        result = st.session_state.last_result
        st.write(f"### {result['feedback']}")
        
        if st.button("다음 단계"):
            st.session_state.current_screen = SCREEN_IMPROVEMENT
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT:
        st.header("질문 개선")
        user_input = st.text_input("개선된 질문을 입력하세요", value=st.session_state.user_question)
        
        if st.button("제출"):
            if not user_input.strip():
                st.warning("질문을 입력해주세요!")
            else:
                st.session_state.user_question = user_input
                st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT
                st.rerun()
    
    elif st.session_state.current_screen == SCREEN_IMPROVEMENT_RESULT:
        st.header("개선 결과")
        st.success("훌륭해요! 질문이 개선되었습니다.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 원래 질문")
            st.caption(st.session_state.user_question)
        with col2:
            st.markdown("### 개선된 질문")
            st.caption(st.session_state.improved_question)
        
        if st.button("세션 결과 보기"):
            st.session_state.current_screen = SCREEN_SESSION_RESULT
            st.rerun()
    
    elif st.session_state.current_screen == SCREEN_SESSION_RESULT:
        st.header("세션 결과")
        session_data = api_session_result()
        st.json(session_data)
        
        if st.button("다시 시작"):
            api_session_start()
            st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE
            st.rerun()

if __name__ == "__main__":
    main()
