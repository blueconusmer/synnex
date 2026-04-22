# 시넥스 질문력 Co-Learner AI Agent Team Skeleton

이 저장소는 질문력 Co-Learner 서비스를 직접 완성하기 위한 저장소가 아니라, 그 서비스를 만들어낼 수 있는 **AI Agent 팀의 최소 구현 뼈대**를 정리하고 검증하기 위한 저장소다.

기준 문서(single source of truth)는 [docs/project_context.md](docs/project_context.md)다. 프로젝트 목적, 현재 단계, 팀 구조, Agent 역할, 산출물 방향은 모두 이 문서를 따른다.

## 왜 지금은 1단계 팀빌딩에 집중하는가

현재 단계는 `1단계: AI 팀빌딩`이다. 지금 중요한 것은 완성형 질문력 챗봇을 빠르게 만드는 것이 아니라, 짧은 일정 안에서 서비스 제작에 필요한 AI 협업 구조가 실제로 작동하는지 검증하는 것이다.

따라서 이 저장소는 아래에 집중한다.

- 역할 기반 Agent 팀 구조 정의
- Agent별 입력값/출력값 뼈대 정리
- 순차 실행형 파이프라인 구성
- 최소 1회 end-to-end 실행 가능한 구조 준비
- 서비스 제작용 산출물 문서화

아래 항목은 현재 필수 범위가 아니다.

- 실제 외부 LLM API 연동
- 완성형 프로덕션 챗봇
- 로그인, DB, 고도화 개인화
- 높은 완성도의 UI

## 팀 구성 Agent 5개

### 1. Product Planner Agent

프로젝트의 문제 정의, 목표, 타깃 사용자, MVP 범위, 제외 범위, 기본 사용자 흐름을 정리한다.

### 2. Question Power Designer Agent

질문력 Agent의 역할, 질문 개선 원칙, 금지사항, 프롬프트 초안, few-shot 예시 방향을 설계한다.

### 3. Quest Designer Agent

사용자가 질문을 더 좋게 만들기 위해 수행하는 퀘스트 유형, 흐름, 인터랙션 방식을 설계한다.

### 4. Growth Mapping Agent

퀘스트 결과를 질문력 성장, 점수, 피드백 메시지 구조로 연결하는 로직을 설계한다.

### 5. Builder & QA Agent

앞선 Agent들의 산출물을 통합하고, 구현 메모, QA 체크리스트, 리스크 정리 등 실제 제작 준비물을 만든다.

## 전체 실행 흐름 개요

현재 저장소는 순차 실행형 멀티에이전트 파이프라인을 기본 구현 방향으로 둔다.

1. Product Planner Agent가 프로젝트 방향과 범위를 정리한다.
2. Question Power Designer Agent가 질문력 Agent의 성격과 규칙을 설계한다.
3. Quest Designer Agent가 사용자 상호작용 구조를 설계한다.
4. Growth Mapping Agent가 성장 및 피드백 로직을 설계한다.
5. Builder & QA Agent가 결과를 통합하고 구현/검수 산출물로 정리한다.

현재 포함된 Python 골격은 실제 LLM 호출 없이 위 흐름을 구조화된 JSON 산출물로 흘려보내는 최소 데모를 제공한다.

## 저장소 구조

```text
.
├── agents/          # Agent 클래스와 순차 파이프라인 골격
├── app.py           # Streamlit 데모 레이어
├── docs/            # 기준 문서와 보조 설명 문서
├── examples/        # 예시 입력값
├── main.py          # 현재 기준 최소 end-to-end 실행 엔트리포인트
├── outputs/         # 실행 산출물 저장 위치
├── prompts/         # Agent별 프롬프트 초안 자리
├── schemas/         # Agent 입출력 스키마
├── pyproject.toml   # 최소 Python 프로젝트 설정
└── run_pipeline.py  # 순차 파이프라인 데모 엔트리포인트
```

## 설치 방법

Python 3.11 이상 기준으로 아래처럼 가상환경을 만든 뒤 설치한다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

환경에 따라 `streamlit`가 바로 잡히지 않으면 아래를 한 번 더 실행한다.

```bash
.venv/bin/python -m pip install streamlit
```

## 순차 실행 방법

최소 end-to-end 파이프라인은 아래 명령으로 실행한다.

```bash
.venv/bin/python main.py
```

실행 시 아래 순서로 Agent가 순차 실행된다.

1. `Product Planner Agent`
2. `Question Power Designer Agent`
3. `Quest Designer Agent`
4. `Growth Mapping Agent`
5. `Builder & QA Agent`

## Outputs 확인 방법

실행이 끝나면 `outputs/` 아래에 아래 파일이 생성된다.

- `planner_output.json`
- `question_output.json`
- `quest_output.json`
- `growth_output.json`
- `builder_qa_output.json`
- `final_summary.md`

기존 `run_pipeline.py`는 초기 데모 엔트리포인트로 남겨 두고, 현재 기준 최소 실행 파이프라인은 `main.py`를 사용한다.

## Streamlit 데모 실행 방법

Streamlit 데모는 기존 파이프라인 산출물을 읽어 질문 Before / After 개선 경험을 보여준다.

먼저 파이프라인 산출물을 준비한다.

```bash
.venv/bin/python main.py
```

그 다음 Streamlit 앱을 실행한다.

```bash
.venv/bin/python -m streamlit run app.py
```

## 데모가 보여주는 핵심 흐름

1. 사용자가 모호한 질문을 입력한다.
2. 챗봇이 질문 개선을 위해 한 번 되묻는다.
3. 사용자가 추가 정보를 입력한다.
4. 앱이 개선된 질문을 생성한다.
5. 화면에 `Before 질문`, `After 질문`, `왜 더 좋아졌는지`, `칭찬 메시지`를 보여준다.

현재 데모는 `outputs/planner_output.json`, `outputs/question_output.json`, `outputs/quest_output.json`, `outputs/growth_output.json`, `outputs/final_summary.md`를 읽어 설명과 기준을 보완하고, 부족한 부분은 rule-based fallback 로직으로 채운다.

## 향후 확장 가능성

현재 저장소는 과설계 없이 최소 골격만 포함한다. 이후 단계에서 아래 방향으로 확장할 수 있다.

### 순차 파이프라인

현재 구조를 유지하면서 Agent별 입력/출력 스키마를 더 엄격히 만들고, 실패 시 재실행 규칙이나 검증 단계를 추가할 수 있다.

### Streamlit 데모

Layer 2로 간단한 데모 UI를 붙여 사용자 입력과 Agent 산출물을 시각적으로 확인할 수 있다.

### Orchestrator

필요해지면 경량 오케스트레이터를 추가해 Agent 실행, 파일 저장, 검증, 요약을 좀 더 체계적으로 관리할 수 있다.
