# QA Report

- Alignment status: WARN

## Input Intake
- Status: NEEDS_PLANNING_REVIEW
- Auto fixes: 7
- Planning review items: 1
- Issues: 0
- Content distribution: {'need_specificity': 1, 'need_context': 1, 'need_purpose': 1, 'completed': 1}

## Input Intake Warning
- content_spec.total_count: mode.allowed_values 개수를 total_count 실행값으로 사용했으나 mode 수와 콘텐츠 수는 동일하다고 자동 확정할 수 없습니다.

## Checklist
- interaction_mode 확인: coaching
- interaction_mode 추론 이유: coaching markers detected with non-quiz-like content type marker profile: coaching=질문 입력, 되묻기, coaching, /api/chat; quiz=정답
- interaction_units 수 확인: 9
- interaction_type 분포 확인: coaching_feedback 3 + feedback 5 + free_text_input 1
- QuizItem 하위 호환 사용 여부: NO
- 총 문제 수 확인: N/A (interaction-unit primary mode)
- 세션 구성 확인: interaction_units 순서와 next_step 기준
- N/A (interaction-unit primary mode)
- learning_dimension 허용값 여부: N/A (quiz semantic validator not required)
- semantic validator 통과 여부: N/A (interaction-unit primary mode)
- 재생성 발생 여부: N/A (quiz regeneration path not used)
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
- cycle 2: REQUIREMENT_MAPPING -> RETRY_RECOMMENDED
- cycle 3: CONTENT_INTERACTION -> RETRY_RECOMMENDED
