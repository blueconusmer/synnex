# Change Log

- Prototype Builder Agent는 live 실행 안정성을 위해 검증된 Streamlit 템플릿을 사용하도록 정규화되었다.
- QA & Alignment Agent는 현재 단계에서 deterministic summary를 생성한다.
- 2026-04-26 live 재실행에서 `quiz_contents.json`의 `quiz_type`은 4개 상호작용 유형으로 정규화되었다.
- 같은 실행에서 `구체성/맥락성/목적성/종합성`은 `learning_dimension` 필드로 분리되었다.
- 최신 live 결과는 총 8문항, 4개 유형, 유형별 2문항 계약을 충족한다.
