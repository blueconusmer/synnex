# QA Report

- Alignment status: WARN

## Input Intake
- Status: AUTO_FIXED
- Auto fixes: 5
- Planning review items: 0
- Issues: 0
- Content distribution: {'multiple_choice': 1, 'question_improvement': 2}

## Checklist
- 총 문제 수 확인: 3
- 세션 구성 확인: multiple_choice 1 + question_improvement 2
- configured content type 수(2) 일치 여부: PASS
- learning_dimension 허용값 여부: PASS
- semantic validator 통과 여부: PASS
- 재생성 발생 여부: NO
- app.py Streamlit smoke test 여부: PASS
- package pytest.py 통과 여부: PASS
- Prototype Builder LLM 생성 여부: fallback_template
- fallback template 사용 여부: YES
- app.py가 서비스별 콘텐츠 파일을 읽도록 생성되었는지 확인
- 실행 로그와 변경 로그가 생성되었는지 확인

## Issues
- LLM-generated app.py did not complete successfully; fallback template was used.
