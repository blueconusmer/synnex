# Change Log

- 2026-04-26 live 실행에서 Upstage Solar Pro2를 사용해 `main.py`를 1회 실행했다.
- 첫 live 시도에서는 `Content & Interaction Agent`가 `ContentInteractionOutput` 대신 JSON schema를 반환해 validation에 실패했다.
- 이를 보완하기 위해 LLM client에 schema-echo retry instruction을 추가하고, implementation output의 `agent` 필드를 optional로 완화했다.
- 다음 live 시도에서는 `Prototype Builder Agent` 단계에서 LLM 응답 지연으로 timeout이 발생했다.
- Prototype Builder Agent는 live 실행 안정성을 위해 검증된 Streamlit 템플릿을 사용하도록 정규화되었다.
- QA & Alignment Agent는 현재 단계에서 deterministic summary를 생성한다.
- 이후 live 콘텐츠 생성 결과 중 일부 문항의 선택지가 2개뿐인 사례가 있어, 최소 3개 선택지 보정 로직을 추가했다.
- 최종 live 실행에서는 `quiz_contents.json`, `prototype_builder_output.json`, `run_test_and_fix_output.json`, `qa_alignment_output.json`, `qa_report.md`, `final_summary.md`가 정상 생성되었고 `app.py`의 py_compile 및 Streamlit smoke test가 통과했다.
