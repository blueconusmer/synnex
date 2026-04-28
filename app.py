import streamlit as st
import json
import os
import uuid
from datetime import datetime

# Load content data
CONTENT_PATH = 'question_quest_contents.json'
if not os.path.exists(CONTENT_PATH):
    with open('outputs/question_quest_contents.json') as f:
        contents = json.load(f)
else:
    with open(CONTENT_PATH) as f:
        contents = json.load(f)

# Mock user progress
if 'user_progress' not in st.session_state:
    st.session_state.user_progress = {
        'cumulative_score': 0,
        'current_grade': 'bronze',
        'completed_session_count': 0
    }

# Session state initialization
if 'session' not in st.session_state:
    st.session_state.session = {
        'session_id': str(uuid.uuid4()),
        'quests': [
            contents['items'][0],  # Q001 (multiple_choice)
            contents['items'][1],  # Q002 (question_improvement)
            contents['items'][2]   # Q003 (question_improvement)
        ],
        'answers': [],
        'current_quest_index': 0,
        'session_score': 0,
        'status': 'in_progress'
    }

# Grade thresholds
GRADE_THRESHOLDS = {
    'bronze': 0,
    'silver': 100,
    'gold': 300,
    'platinum': 600
}

def determine_grade(score):
    for grade, threshold in sorted(GRADE_THRESHOLDS.items(), key=lambda x: -x[1]):
        if score >= threshold:
            return grade
    return 'bronze'

def api_session_start():
    session = st.session_state.session
    return {
        'session_id': session['session_id'],
        'quests': session['quests'],
        'user_progress': st.session_state.user_progress
    }

def evaluate_multiple_choice(quest, user_response):
    correct_index = quest['choices'].index(quest['correct_choice'])
    is_correct = (user_response == correct_index)

    feedback = quest['explanation']
    if is_correct:
        feedback = f"정답입니다! {feedback}"
        earned_score = 20
    else:
        feedback = f"이 질문도 좋지만 더 명확한 선택지가 있어요. {feedback}"
        earned_score = 5

    return {
        'evaluation': {
            'evaluation_type': 'correctness',
            'is_correct': is_correct,
            'feedback': feedback
        },
        'earned_score': earned_score,
        'correct_option_index': correct_index,
        'is_session_complete': False
    }

def evaluate_question_improvement(quest, user_response):
    # Rule-based evaluation instead of LLM
    specificity = 'excellent' if any(kw in user_response.lower() for kw in ['무엇', '어떤', '어떤', '어떤', '어떤', '어떤', '어떤', '어떤', '어떤', '어떤']) else 'needs_work'
    context = 'excellent' if any(kw in user_response.lower() for kw in ['숙제', '시험', '과제', '수업', '공부', '학교', '학원']) else 'needs_work'
    purpose = 'excellent' if any(kw in user_response.lower() for kw in ['설명', '예시', '풀이', '방법', '과정', '단계', '이유', '배경']) else 'needs_work'

    if all([specificity == 'excellent', context == 'excellent', purpose == 'excellent']):
        overall = 'excellent'
        earned_score = 30
        feedback = "질문이 아주 명확해졌어요! 무엇을, 왜, 어떻게가 모두 잘 드러나 있어요."
    elif any([specificity == 'needs_work', context == 'needs_work', purpose == 'needs_work']):
        overall = 'needs_work'
        earned_score = 10
        feedback = "한 부분이 더 명확해지면 좋겠어요. " + {
            'specificity': "무엇을 묻는지 더 명확히 해주세요",
            'context': "왜 필요한지 상황을 알려주세요",
            'purpose': "어떤 도움을 원하는지 알려주세요"
        }[min([specificity, context, purpose], key=lambda x: ['needs_work', 'good', 'excellent'].index(x))]
    else:
        overall = 'good'
        earned_score = 20
        feedback = "좋아졌어요! " + {
            'specificity': "무엇을 묻는지 더 명확해졌어요",
            'context': "왜 필요한지 더 명확해졌어요",
            'purpose': "어떤 도움을 원하는지 더 명확해졌어요"
        }[max([specificity, context, purpose], key=lambda x: ['needs_work', 'good', 'excellent'].index(x))]

    return {
        'evaluation': {
            'evaluation_type': 'rubric',
            'rubric_result': {
                'specificity': specificity,
                'context': context,
                'purpose': purpose,
                'overall': overall
            },
            'feedback': feedback
        },
        'earned_score': earned_score,
        'is_session_complete': (st.session_state.session['current_quest_index'] == 2)
    }

def api_quest_submit(quest_id, user_response):
    session = st.session_state.session
    quest = next(q for q in session['quests'] if q['item_id'] == quest_id)

    if quest['quiz_type'] == 'multiple_choice':
        result = evaluate_multiple_choice(quest, user_response)
    else:
        result = evaluate_question_improvement(quest, user_response)

    session['answers'].append({
        'answer_id': str(uuid.uuid4()),
        'session_id': session['session_id'],
        'quest_id': quest_id,
        'user_response': user_response,
        'evaluation': result['evaluation'],
        'earned_score': result['earned_score'],
        'submitted_at': datetime.now().isoformat()
    })

    session['session_score'] += result['earned_score']
    session['current_quest_index'] += 1

    if result['is_session_complete']:
        session['status'] = 'completed'
        st.session_state.user_progress['cumulative_score'] += session['session_score']
        st.session_state.user_progress['completed_session_count'] += 1
        new_grade = determine_grade(st.session_state.user_progress['cumulative_score'])
        if new_grade != st.session_state.user_progress['current_grade']:
            st.session_state.user_progress['current_grade'] = new_grade
            st.session_state.grade_up_event = True
        else:
            st.session_state.grade_up_event = False

    return result

def api_session_result():
    session = st.session_state.session
    return {
        'session_id': session['session_id'],
        'session_score': session['session_score'],
        'user_progress': st.session_state.user_progress,
        'grade_up_event': getattr(st.session_state, 'grade_up_event', False)
    }

# Main app logic
if st.session_state.session['status'] == 'in_progress':
    current_quest = st.session_state.session['quests'][st.session_state.session['current_quest_index']]

    if current_quest['quiz_type'] == 'multiple_choice':
        st.title(f"퀘스트 {st.session_state.session['current_quest_index'] + 1} / 3")
        st.markdown(f"**학습 맥락**: {current_quest['topic_context']}")
        st.markdown(f"**원본 질문**: {current_quest['original_question']}")
        st.markdown("이 질문을 더 좋게 바꾼 선택지는 무엇일까요?")

        choices = current_quest['choices']
        selected_choice = st.radio("선택지", choices, key='multiple_choice')

        if st.button("제출"):
            if selected_choice is None:
                st.error("선택지를 골라주세요")
            else:
                result = api_quest_submit(current_quest['item_id'], choices.index(selected_choice))
                st.session_state.evaluation = result
                st.session_state.current_quest = current_quest
                st.experimental_rerun()

    elif current_quest['quiz_type'] == 'question_improvement':
        st.title(f"퀘스트 {st.session_state.session['current_quest_index'] + 1} / 3")
        st.markdown(f"**학습 맥락**: {current_quest['topic_context']}")
        st.markdown(f"**원본 질문**: {current_quest['original_question']}")
        st.markdown("이 질문을 더 명확하게 바꿔보세요. 무엇을, 왜, 어떻게가 들어가면 좋아요.")

        user_response = st.text_area("개선된 질문", key='question_improvement', height=100)
        char_count = len(user_response)
        st.markdown(f"{char_count} / 300")

        if st.button("제출"):
            if not user_response or char_count < 10:
                st.error("조금 더 자세히 작성해주세요 (최소 10자)")
            else:
                result = api_quest_submit(current_quest['item_id'], user_response)
                st.session_state.evaluation = result
                st.session_state.current_quest = current_quest
                st.experimental_rerun()

    if 'evaluation' in st.session_state:
        evaluation = st.session_state.evaluation
        current_quest = st.session_state.current_quest

        if current_quest['quiz_type'] == 'multiple_choice':
            st.title("객관식 결과")
            if evaluation['evaluation']['is_correct']:
                st.markdown("🎉 정답입니다!")
            else:
                st.markdown("👍 이 질문도 좋아요")

            st.markdown(f"**당신이 선택한 답변**: {current_quest['choices'][evaluation['evaluation']['is_correct']]}")
            st.markdown(f"**정답**: {current_quest['correct_choice']}")
            st.markdown(f"**해설**: {evaluation['evaluation']['feedback']}")
            st.markdown(f"**획득 점수**: +{evaluation['earned_score']}점")

            if st.button("다음 퀘스트로"):
                del st.session_state.evaluation
                del st.session_state.current_quest
                st.experimental_rerun()

        elif current_quest['quiz_type'] == 'question_improvement':
            st.title("개선형 결과")
            if evaluation['evaluation']['rubric_result']['overall'] == 'excellent':
                st.markdown("😎 아주 명확해졌어요!")
            elif evaluation['evaluation']['rubric_result']['overall'] == 'good':
                st.markdown("👍 좋아졌어요!")
            else:
                st.markdown("⚠️ 한 부분만 더 보완해볼까요?")

            st.markdown(f"**Before**: {current_quest['original_question']}")
            st.markdown(f"**After**: {evaluation['evaluation']['feedback']}")

            rubric = evaluation['evaluation']['rubric_result']
            st.markdown("### 루브릭 결과")
            for dimension, score in rubric.items():
                if dimension != 'overall':
                    st.markdown(f"- {dimension}: {'✅' if score == 'excellent' else '🔺' if score == 'good' else '❌'}")

            st.markdown(f"**획득 점수**: +{evaluation['earned_score']}점")

            if st.button("다음 퀘스트로" if st.session_state.session['current_quest_index'] < 2 else "결과 보기"):
                del st.session_state.evaluation
                del st.session_state.current_quest
                st.experimental_rerun()

else:
    result = api_session_result()
    st.title("세션 결과")
    st.markdown(f"**이번 세션 점수**: +{result['session_score']}점")
    st.markdown(f"**누적 총점**: {result['user_progress']['cumulative_score']}점")
    st.markdown(f"**현재 등급**: {result['user_progress']['current_grade']}")

    if result['grade_up_event']:
        st.balloons()
        st.markdown(f"🎉 축하해요! 이제 {result['user_progress']['current_grade']} 단계예요")

    if st.button("새 세션 시작"):
        st.session_state.session = {
            'session_id': str(uuid.uuid4()),
            'quests': [
                contents['items'][0],
                contents['items'][1],
                contents['items'][2]
            ],
            'answers': [],
            'current_quest_index': 0,
            'session_score': 0,
            'status': 'in_progress'
        }
        st.experimental_rerun()

    st.button("종료")
