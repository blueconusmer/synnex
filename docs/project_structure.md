# 프로젝트 구조 메모

이 문서는 `docs/project_context.md`를 보조하는 구조 설명 문서다.
현재 active 구조는 **교육 서비스 구현 전문 AI Agent 팀** 기준이며,
기존 질문력 기획용 skeleton은 legacy reference로 남겨 둔다.

## Active 구조

- `inputs/`: 구현팀이 받는 원본 명세서
- `clients/`: 실제 실행 경로에서 사용하는 LLM client
- `agents/implementation/`: 6개 구현 Agent runner
- `schemas/implementation/`: 구현팀 input/output Pydantic 모델
- `prompts/implementation/`: Agent별 prompt 초안
- `orchestrator/`: 순차 실행 파이프라인, app source helper
- `outputs/`: Agent 산출물, 실행 로그, QA 결과

## Legacy 구조

아래는 이전 질문력 기획용 skeleton이며, 현재 active path는 아니다.

- `agents/` 루트의 기존 5-Agent 파일
- `schemas/` 루트의 기존 5-Agent schema
- `run_pipeline.py`
- 질문 Before/After 중심 예시 outputs

## 구현 원칙

- `docs/project_context.md`를 single source of truth로 사용한다.
- runtime 실행은 환경변수 기반 LLM client를 사용한다.
- 자동 테스트는 deterministic fake/mock LLM client를 사용한다.
- 기존 파일은 삭제하지 않고, 새 active path를 추가하는 방식으로 확장한다.
