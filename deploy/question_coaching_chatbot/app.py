import streamlit as st
import json
import os
from pathlib import Path

# Configuration
APP_DIR = Path(__file__).parent
CONTENT_FILENAME = "Question_Coaching_Chatbot_contents.json"
OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME
FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME
CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]

# Screen constants
SCREEN_START = "start"
SCREEN_INPUT = "input"
SCREEN_FOLLOW_UP = "follow_up"
SCREEN_RESULT = "result"
SCREEN_ERROR = "error"

# Initialize session state
if "current_screen" not in st.session_state:
    st.session_state.current_screen = SCREEN_START
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0
if "original_question" not in st.session_state:
    st.session_state.original_question = ""
if "latest_question" not in st.session_state:
    st.session_state.latest_question = ""
if "improved_question" not in st.session_state:
    st.session_state.improved_question = ""
if "interaction_units" not in st.session_state:
    st.session_state.interaction_units = []

# Resolve content path
def resolve_content_path() -> Path:
    for path in CONTENT_CANDIDATE_PATHS:
        if path.exists():
            return path
    return None

# Load content
content_path = resolve_content_path()
if content_path:
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)
    st.session_state.interaction_units = content.get("interaction_units", [])
else:
    st.error("콘텐츠 파일을 찾을 수 없습니다. 'outputs/Question_Coaching_Chatbot_contents.json' 또는 루트 디렉토리에 'Question_Coaching_Chatbot_contents.json' 파일이 있는지 확인하세요.")
    st.stop()

# API functions

def api_chat_submit(user_question: str, session_id: str = "1", turn_count: int = 0) -> dict:
    """Simulates API call for question evaluation"""
    # Mock evaluation based on content
    units = st.session_state.interaction_units
    current_unit = next((u for u in units if u["unit_id"] == f"retry_00{turn_count}"), None)
    
    if not user_question.strip():
        return {
            "mode": "error",
            "message": "질문을 입력해주세요"
        }
    
    # Simple evaluation logic based on keywords
    has_specificity = any(kw in user_question for kw in ["수학", "국어", "과학", "사회"])
    has_context = any(kw in user_question for kw in ["시험", "숙제", "수행평가", "발표"])
    has_purpose = any(kw in user_question for kw in ["설명", "예시", "비교", "풀이"])
    
    if turn_count == 0 and not has_specificity:
        return {
            "mode": "need_specificity",
            "diagnosis_dimension": "구체성",
            "diagnosis": "질문하려는 주제나 대상이 아직 분명하지 않아요.",
            "dimension_explanation": "무엇을 묻는지 분명해야 AI도 정확한 도움을 줄 수 있어요.",
            "follow_up_question": "어떤 단원이나 어떤 문제가 어려운지 한 가지만 먼저 말해줄래?",
            "improvement_points": [
                "과목이나 단원을 먼저 적기",
                "헷갈리는 문제 유형을 한 가지로 좁히기"
            ],
            "example_questions": [
                {
                    "weak_question": "수학 모르겠어요",
                    "improved_question": "이차방정식 문제를 풀 때 인수분해를 언제 써야 하는지 알려줘.",
                    "why_it_works": "무슨 단원인지와 무엇이 궁금한지가 함께 보여."
                }
            ],
            "encouragement_message": "조금만 더 구체적으로 말하면 훨씬 좋은 질문이 될 수 있어!",
            "next_action": "ask_more"
        }
    elif turn_count == 1 and not has_context:
        return {
            "mode": "need_context",
            "diagnosis_dimension": "맥락성",
            "diagnosis": "어떤 상황에서 이 도움이 필요한지 아직 잘 안 보여.",
            "dimension_explanation": "숙제인지, 시험 준비인지, 숙제 중인지 같은 배경이 있으면 필요한 설명 방식이 달라져.",
            "follow_up_question": "수업 복습 중인지, 시험 대비인지, 숙제 중인지 알려주면 더 잘 도와줄 수 있어!",
            "improvement_points": [
                "왜 지금 이 질문을 하는지 적기",
                "수업/숙제/시험 같은 상황 넣기"
            ],
            "example_questions": [
                {
                    "weak_question": "삼각함수 알려줘",
                    "improved_question": "시험 준비 중인데 삼각함수 기본 공식을 한 번에 정리해서 설명해줘.",
                    "why_it_works": "상황이 들어가서 어떤 도움을 원하는지 더 분명해졌어."
                }
            ],
            "encouragement_message": "배경을 조금만 더 알려주면 더 딱 맞는 도움을 받을 수 있어!",
            "next_action": "ask_more"
        }
    elif turn_count == 2 and not has_purpose:
        return {
            "mode": "need_purpose",
            "diagnosis_dimension": "목적성",
            "diagnosis": "무엇을 원하는지까지 적으면 더 좋은 질문이 될 수 있어.",
            "dimension_explanation": "설명, 예시, 비교처럼 원하는 답의 모양이 보이면 AI가 더 정확하게 답할 수 있어.",
            "follow_up_question": "이유를 설명해주길 원하는지, 예시를 들어주길 원하는지 알려줄래?",
            "improvement_points": [
                "설명해줘 / 예시를 들어줘처럼 원하는 답의 형태 적기",
                "한 문장으로 어떤 도움을 받고 싶은지 마무리하기"
            ],
            "example_questions": [
                {
                    "weak_question": "국어 숙제인데 '내 마음은 호수요'가 무슨 뜻인지 궁금해",
                    "improved_question": "국어 숙제인데 '내 마음은 호수요'에서 '호수'가 어떤 점에서 비유 표현인지 이유를 설명해줘.",
                    "why_it_works": "상황과 함께 원하는 답의 형태가 보여."
                }
            ],
            "encouragement_message": "이제 거의 다 왔어! 원하는 도움만 더 말해주면 돼.",
            "next_action": "ask_more"
        }
    else:
        # Final improvement
        improved = user_question
        if not has_specificity:
            improved = "수학/" + improved
        if not has_context:
            improved = improved + "/학교 시험 문제"
        if not has_purpose:
            improved = improved + "/단계별 풀이 과정"
        
        return {
            "mode": "completed",
            "improved_question": improved,
            "improvement_points": [
                "주제, 상황, 원하는 답의 형태가 모두 포함되었습니다.",
                "AI에게 질문하기에 적합한 형태입니다."
            ],
            "example_questions": [
                {
                    "weak_question": "수학 모르겠어요",
                    "improved_question": "이차방정식 문제를 풀 때 인수분해를 언제 써야 하는지 알려줘.",
                    "why_it_works": "무슨 단원인지와 무엇이 궁금한지가 함께 보여."
                }
            ],
            "next_step_suggestions": [
                "과목이나 상황을 먼저 적어 보기",
                "설명, 예시, 비교 중 원하는 답 형태를 한 단어로 먼저 정하기"
            ],
            "encouragement_message": "축하합니다! 이제 질문만 봐도 무엇을 알고 싶은지 분명히 보여!",
            "next_action": "show_result"
        }

def show_start_screen():
    st.session_state.current_screen = SCREEN_INPUT
    st.rerun()

def show_input_screen():
    st.title("📚 질문 코칭 챗봇")
    st.markdown("좋은 질문은 주제, 상황, 원하는 도움을 함께 말해요.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### ✅ 좋은 질문 체크리스트")
        st.markdown("- 무엇이 궁금한지 분명한가?")
        st.markdown("- 어떤 상황에서 필요한 질문인지 보이는가?")
        st.markdown("- 어떤 도움을 원하는지 드러나는가?")
    
    with col2:
        st.markdown("### 💡 시작 예시 질문")
        st.markdown("- 국어 수행평가에서 비유 표현을 설명할 때 어떤 순서로 쓰면 좋을지 알려줘.")
        st.markdown("- 과학 실험 보고서에서 광합성 속도가 왜 달라지는지 이유를 설명해줘.")
        st.markdown("- 수학 시험 준비 중인데 이차방정식 풀이 방법을 비교해줘.")
        st.markdown("- 사회 발표를 위해 기후 변화가 우리 생활에 미치는 영향을 사례와 함께 설명해줘.")
    
    user_question = st.text_input("질문을 자유롭게 입력해주세요", value=st.session_state.latest_question if st.session_state.latest_question else "")
    if st.button("제출"):
        if not user_question.strip():
            st.session_state.current_screen = SCREEN_ERROR
            st.rerun()
        else:
            if st.session_state.turn_count == 0:
                st.session_state.original_question = user_question
            st.session_state.latest_question = user_question
            response = api_chat_submit(user_question, turn_count=st.session_state.turn_count)
            
            if response["mode"] == "error":
                st.session_state.current_screen = SCREEN_ERROR
            elif response["mode"] in ["need_specificity", "need_context", "need_purpose"]:
                st.session_state.current_screen = SCREEN_FOLLOW_UP
                st.session_state.diagnosis = response
            else:  # completed
                st.session_state.current_screen = SCREEN_RESULT
                st.session_state.improved_question = response["improved_question"]
                st.session_state.improvement_points = response["improvement_points"]
                st.session_state.example_questions = response.get("example_questions", [])
                st.session_state.next_step_suggestions = response.get("next_step_suggestions", [])
                st.session_state.encouragement_message = response.get("encouragement_message", "")
            st.rerun()

def show_follow_up_screen():
    diagnosis = st.session_state.diagnosis
    
    st.title(f"🔍 {diagnosis['diagnosis_dimension']} 보완하기")
    st.markdown(f"### 📌 진단: {diagnosis['diagnosis']}")
    st.markdown(f"#### 📚 왜 이 요소를 보완해야 할까요? {diagnosis['dimension_explanation']}")
    st.markdown(f"#### ❓ 다음 질문에 답해 보세요: {diagnosis['follow_up_question']}")
    
    st.markdown("### ✅ 개선 포인트")
    for point in diagnosis["improvement_points"]:
        st.markdown(f"- {point}")
    
    st.markdown("### 📝 예시 질문")
    for example in diagnosis.get("example_questions", []):
        st.markdown(f"- 약한 질문: {example['weak_question']}")
        st.markdown(f"- 개선된 질문: {example['improved_question']}")
        st.markdown(f"- 좋아진 이유: {example['why_it_works']}")
    
    st.markdown(f"#### 🌟 격려 메시지: {diagnosis['encouragement_message']}")
    
    user_question = st.text_input("질문을 다시 작성해 보세요", value=st.session_state.latest_question)
    if st.button("제출"):
        if not user_question.strip():
            st.session_state.current_screen = SCREEN_ERROR
        else:
            st.session_state.latest_question = user_question
            st.session_state.turn_count += 1
            response = api_chat_submit(user_question, turn_count=st.session_state.turn_count)
            
            if response["mode"] == "error":
                st.session_state.current_screen = SCREEN_ERROR
            elif response["mode"] in ["need_specificity", "need_context", "need_purpose"]:
                st.session_state.diagnosis = response
            else:  # completed
                st.session_state.current_screen = SCREEN_RESULT
                st.session_state.improved_question = response["improved_question"]
                st.session_state.improvement_points = response["improvement_points"]
                st.session_state.example_questions = response.get("example_questions", [])
                st.session_state.next_step_suggestions = response.get("next_step_suggestions", [])
                st.session_state.encouragement_message = response.get("encouragement_message", "")
            st.rerun()

def show_result_screen():
    st.title("🎉 완성된 질문")
    st.markdown(f"#### 📌 원래 질문: {st.session_state.original_question}")
    st.markdown(f"#### ✅ 개선된 질문: {st.session_state.improved_question}")
    
    st.markdown("### 📈 개선된 점")
    for point in st.session_state.improvement_points:
        st.markdown(f"- {point}")
    
    st.markdown("### 📚 우수 질문 예시")
    for example in st.session_state.example_questions:
        st.markdown(f"- 약한 질문: {example['weak_question']}")
        st.markdown(f"- 개선된 질문: {example['improved_question']}")
        st.markdown(f"- 좋아진 이유: {example['why_it_works']}")
    
    st.markdown("### 📌 다음 질문 팁")
    for suggestion in st.session_state.next_step_suggestions:
        st.markdown(f"- {suggestion}")
    
    st.markdown(f"#### 🌟 격려 메시지: {st.session_state.encouragement_message}")
    
    if st.button("다시 시도"):
        st.session_state.current_screen = SCREEN_INPUT
        st.session_state.turn_count = 0
        st.session_state.original_question = ""
        st.session_state.latest_question = ""
        st.session_state.improved_question = ""
        st.rerun()

def show_error_screen():
    st.title("❌ 오류")
    st.markdown("질문을 입력해주세요")
    
    st.markdown("### 📚 시작 예시 질문")
    st.markdown("- 국어 수행평가에서 비유 표현을 설명할 때 어떤 순서로 쓰면 좋을지 알려줘.")
    st.markdown("- 과학 실험 보고서에서 광합성 속도가 왜 달라지는지 이유를 설명해줘.")
    st.markdown("- 수학 시험 준비 중인데 이차방정식 풀이 방법을 비교해줘.")
    st.markdown("- 사회 발표를 위해 기후 변화가 우리 생활에 미치는 영향을 사례와 함께 설명해줘.")
    
    if st.button("재시도"):
        st.session_state.current_screen = SCREEN_INPUT
        st.rerun()

# Main app
if st.session_state.current_screen == SCREEN_START:
    show_start_screen()
elif st.session_state.current_screen == SCREEN_INPUT:
    show_input_screen()
elif st.session_state.current_screen == SCREEN_FOLLOW_UP:
    show_follow_up_screen()
elif st.session_state.current_screen == SCREEN_RESULT:
    show_result_screen()
elif st.session_state.current_screen == SCREEN_ERROR:
    show_error_screen()
