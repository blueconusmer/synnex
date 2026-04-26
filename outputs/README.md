# Outputs Directory

이 디렉토리는 active 6-Agent 구현팀 파이프라인의 실행 결과를 저장하는 위치다.

## Active 결과

현재 `main.py`를 실행하면 아래 active 결과가 생성된다.

- `spec_intake_output.json`
- `requirement_mapping_output.json`
- `quiz_contents.json`
- `prototype_builder_output.json`
- `run_test_and_fix_output.json`
- `qa_alignment_output.json`
- `execution_log.txt`
- `qa_report.md`
- `change_log.md`
- `final_summary.md`

## Legacy 결과

아래 파일과 폴더는 이전 question-power skeleton 실행 결과다.

- `planner_output.json`
- `question_output.json`
- `quest_output.json`
- `growth_output.json`
- `builder_qa_output.json`
- `latest_run/`

현재 active 데모인 `app.py`는 위 legacy 결과를 읽지 않고, `quiz_contents.json`만 읽는다.
