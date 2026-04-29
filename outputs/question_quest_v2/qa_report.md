# QA Report

- Alignment status: WARN

## Input Intake
- Status: AUTO_FIXED
- Auto fixes: 7
- Planning review items: 0
- Issues: 0
- Content distribution: {'multiple_choice': 1, 'situation_card': 2, 'question_improvement': 1, 'battle': 1}

## Checklist
- interaction_mode 확인: quiz
- interaction_mode 추론 이유: quiz markers detected: 정답, 점수, 배틀, quest, multiple_choice
- interaction_units 수 확인: 12
- interaction_type 분포 확인: feedback 5 + free_text_input 4 + multiple_choice 1 + score_summary 2
- QuizItem 하위 호환 사용 여부: YES
- 총 문제 수 확인: 5
- 세션 구성 확인: multiple_choice 1 + situation_card 2 + question_improvement 1 + battle 1
- configured content type 수(4) 일치 여부: PASS
- learning_dimension 허용값 여부: PASS
- semantic validator 통과 여부: PASS
- 재생성 발생 여부: NO
- interaction_units 구조 validator 통과 여부: PASS
- app.py Streamlit smoke test 여부: PASS
- package pytest.py 통과 여부: NOT RUN
- Prototype Builder LLM 생성 여부: fallback_template
- fallback template 사용 여부: YES
- app.py가 서비스별 콘텐츠 파일을 읽도록 생성되었는지 확인
- 실행 로그와 변경 로그가 생성되었는지 확인

## Issues
- LLM-generated app.py did not complete successfully; fallback template was used.

## Feedback Loop Summary
- overall_status: NEEDS_HUMAN_REVIEW
- issue_type: APP_GENERATION_FEEDBACK
- target_agent: HUMAN_REVIEW
- retry_count: 3
- llm_judge_used: True
- should_stop: True
- stop_reason: Retry budget was exhausted before the issue was resolved.
- retry_history:
- cycle 1: REQUIREMENT_MAPPING -> RETRY_RECOMMENDED
- cycle 2: CONTENT_INTERACTION -> RETRY_RECOMMENDED
- cycle 3: CONTENT_INTERACTION -> RETRY_RECOMMENDED
