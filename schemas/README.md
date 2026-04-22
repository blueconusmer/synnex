# Schemas Directory

이 디렉토리는 `docs/project_context.md`를 기준으로 Agent 입출력 계약을 정의하는 스키마 파일을 둔다.

현재는 두 종류의 스키마가 함께 존재한다.

- Python 기반 Pydantic 모델: 이후 Agent 구현 단계에서 바로 import 해서 사용할 계약
- `.schema.json` 파일: 초기 구조 초안을 남겨 둔 참고용 JSON Schema

현재 우선 기준은 Python 기반 Pydantic 모델이다. 각 Agent 입력 모델은 앞 단계 출력 모델을 직접 참조하도록 설계되어 있으며, 출력은 JSON 직렬화가 가능한 구조만 사용한다.
