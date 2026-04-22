# Outputs Directory

이 디렉토리는 순차 파이프라인 실행 결과를 저장하는 위치다.

현재 `main.py`를 실행하면 아래 파일이 생성된다.

- `planner_output.json`
- `question_output.json`
- `quest_output.json`
- `growth_output.json`
- `builder_qa_output.json`
- `final_summary.md`

기존 데모 파이프라인 결과는 `outputs/latest_run/` 아래에 유지될 수 있다.

이 구조는 이후 Streamlit 데모에서 그대로 읽어 오기 쉽도록 단순한 파일 이름을 유지한다.
