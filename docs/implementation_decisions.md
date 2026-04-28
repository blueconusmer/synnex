# Implementation Decisions

이 문서는 구현 중 기존 계획과 달라진 판단이나,
구조적 이유로 선택한 구현 결정을 기록한다.

## 2026-04-26

### 결정 1. 기존 질문력 5-Agent skeleton은 legacy reference로 유지
- 맥락: 저장소에는 이미 질문력 기획용 5-Agent skeleton이 존재했다.
- 결정: 기존 파일은 삭제하지 않고, 새 active path를 `agents/implementation`, `schemas/implementation`, `orchestrator` 기준으로 추가한다.
- 이유: 기존 작업 이력을 보존하면서도 #11의 교육 서비스 구현팀 구조를 명확히 분리하기 위해서다.
- 영향 범위: `main.py`, `app.py`, `README.md`, `docs/project_context.md`, 새 implementation 패키지 전반

### 결정 2. `app.py`는 thin wrapper가 아니라 self-contained Streamlit 앱 코드로 생성
- 맥락: 생성된 `app.py`가 특정 로컬 import 경로에 의존하면 테스트용 임시 workspace에서 깨질 수 있다.
- 결정: Prototype Builder Agent가 생성하는 `app.py`는 `json`, `pathlib`, `streamlit`만으로 동작하는 self-contained 코드 문자열을 사용한다.
- 이유: generated app의 compile/smoke test를 더 단순하고 안정적으로 만들기 위해서다.
- 영향 범위: `agents/implementation/prototype_builder_agent.py`, `orchestrator/app_source.py`, `app.py`, 테스트 코드

### 결정 3. 저장소 기본 `outputs/`는 fake client 기반 샘플 산출물로 시드
- 맥락: runtime 경로는 실제 환경변수 기반 LLM client를 사용하지만, 기본 저장소 상태에서도 Streamlit MVP와 outputs 구조를 바로 확인할 필요가 있다.
- 결정: 자동 테스트에 사용하는 deterministic fake client로 한 번 파이프라인을 실행해 `outputs/quiz_contents.json`, `qa_report.md`, `final_summary.md` 등 active 산출물을 채워 둔다.
- 이유: API 키 없이도 현재 구현 결과와 데모 화면을 바로 확인할 수 있게 하기 위해서다.
- 영향 범위: `outputs/` 아래 active 산출물 전반, `app.py` 기본 데모 확인 흐름

### 결정 4. live 실행에서도 `app.py`는 검증된 템플릿으로 정규화
- 맥락: Prototype Builder Agent가 LLM 응답으로 `app.py`를 직접 생성하면, live run에서 품질 변동으로 compile/smoke test가 흔들릴 수 있다.
- 결정: Builder output에 `app.py`가 있더라도 실제 저장 내용은 현재 검증된 self-contained Streamlit 템플릿으로 정규화한다.
- 이유: 이번 단계의 핵심은 `quiz_contents.json` 기반 MVP 실행 골격 검증이지, 자유 형식 코드 생성 품질 비교가 아니기 때문이다.
- 영향 범위: `agents/implementation/prototype_builder_agent.py`, `prototype_builder_output.json`, live runtime 안정성

### 결정 5. live structured output 실패 시 schema-echo 재시도 보정 추가
- 맥락: Solar Pro2 live 실행에서 `ContentInteractionOutput` 생성 시 모델이 실제 값 대신 JSON schema 자체를 반환했다.
- 결정: LLM client에 validation 실패 시 재시도 프롬프트를 추가하고, 구현 output의 `agent` 필드는 optional로 완화한다.
- 이유: 이번 단계에서 중요한 것은 structured live execution 성공이며, agent 라벨은 후처리로 안정적으로 채울 수 있기 때문이다.
- 영향 범위: `clients/llm.py`, `schemas/implementation/*Output`, live API 안정성

### 결정 6. Builder/QA 단계는 deterministic summary로 고정
- 맥락: Solar Pro2 live 실행에서 고가치 생성 단계는 콘텐츠 생성이고, Builder와 QA는 이미 고정 계약이 강한 후처리 성격이어서 LLM 호출 지연과 timeout 영향을 크게 받았다.
- 결정: `Prototype Builder Agent`는 검증된 Streamlit 템플릿과 runtime notes를 deterministic하게 생성하고, `QA & Alignment Agent`는 upstream outputs와 local checks를 기반으로 deterministic summary를 만든다.
- 이유: 이번 이슈의 목표는 교육 서비스 구현팀의 실행 골격과 live 콘텐츠 생성 검증이며, builder/QA까지 모두 live text generation에 의존할 필요는 없기 때문이다.
- 후속 방향: 후속 이슈에서 builder/QA 단계까지 live generation 범위를 다시 확장할 수 있다. 현재는 MVP 안정성을 우선한 선택이다.
- 영향 범위: `agents/implementation/prototype_builder_agent.py`, `agents/implementation/qa_alignment_agent.py`, live runtime 안정성

### 결정 7. live 퀴즈 콘텐츠는 최소 계약 보정 후 검증
- 맥락: Solar Pro2 live 생성 결과에서 일부 문항이 선택지 2개만 포함하는 등, 핵심 구조는 맞지만 최소 계약을 살짝 벗어나는 사례가 발생했다.
- 결정: 콘텐츠 Agent 후처리에서 `correct_choice` 보정, 최소 3개 선택지 보정, answer/explanation/learning point 매핑 보정을 수행한 뒤 계약 검증을 실행한다.
- 이유: 이번 단계는 교육 콘텐츠 자동 생성의 완전한 미세 품질보다, 8문항 구조와 MVP 실행 가능성을 검증하는 것이 더 중요하기 때문이다.
- 영향 범위: `agents/implementation/content_interaction_agent.py`, live `quiz_contents.json` 안정성

## 2026-04-28

### 결정 8. `target_framework`는 Streamlit 우선, 미지원 프레임워크는 명시적 중단
- 맥락: 후속 React/FastAPI/Next.js 확장을 위해 Prototype Builder가 어떤 프레임워크를 대상으로 생성해야 하는지 알아야 한다.
- 결정: runtime 기준 필드는 `ImplementationSpec.target_framework`로 두고, 현재 지원값은 `streamlit`만 허용한다. 다른 값은 fallback 생성 없이 unsupported output/log를 남긴 뒤 local checks 전에 중단한다.
- 이유: 미지원 프레임워크를 Streamlit으로 암묵 대체하면 실제 지원 범위를 오해할 수 있기 때문이다.
- 영향 범위: `schemas/implementation/implementation_spec.py`, `schemas/planning_package/package.py`, `agents/implementation/prototype_builder_agent.py`, `orchestrator/pipeline.py`
