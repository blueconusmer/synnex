# 교육 서비스 구현 전문 AI Agent Team Skeleton

이 저장소는 교육 서비스 구현 명세서를 입력받아 **교육 콘텐츠**, **Streamlit MVP 코드**, **실행 로그**, **QA 결과**를 생성하는 **교육 서비스 구현 전문 AI Agent 팀**의 실행 골격을 구현하기 위한 저장소다.

기준 문서는 [docs/project_context.md](docs/project_context.md)다. 현재 active 구조는 6-Agent 구현팀 기준이며, 기존 질문력 기획용 skeleton은 legacy reference로 남겨 둔다.

## 현재 검증 사례

현재 첫 검증 사례는 **질문력 향상 퀴즈 서비스 MVP**다.

- 구현팀 정체성은 범용 교육 서비스 구현팀으로 유지한다.
- 기본 입력은 [inputs/quiz_service_spec.md](inputs/quiz_service_spec.md)다.
- 이번 MVP acceptance는 `4개 퀴즈 유형 × 각 2문제 = 총 8문제`다.

## 6-Agent 구조

1. `Spec Intake Agent / 구현 명세서 분석 Agent`
2. `Requirement Mapping Agent / 구현 요구사항 정리 Agent`
3. `Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent`
4. `Prototype Builder Agent / MVP 서비스 코드 생성 Agent`
5. `Run Test And Fix Agent / 실행·테스트·수정 Agent`
6. `QA & Alignment Agent / 최종 검수·정합성 확인 Agent`

## 전체 실행 흐름

1. Markdown 구현 명세서를 읽는다.
2. 구현 명세서 분석 Agent가 명세를 구조화한다.
3. 구현 요구사항 정리 Agent가 구현 계약과 파일 계획을 만든다.
4. 교육 콘텐츠·상호작용 생성 Agent가 퀴즈 콘텐츠를 만든다.
5. MVP 서비스 코드 생성 Agent가 Streamlit `app.py`를 만든다.
6. 실행·테스트·수정 Agent가 compile/smoke test 결과를 남긴다.
7. 최종 검수·정합성 확인 Agent가 QA 리포트와 변경 로그를 만든다.

## 주요 경로

```text
.
├── inputs/                    # 원본 구현 명세서
├── clients/                   # 환경변수 기반 LLM client
├── agents/implementation/     # 6개 구현 Agent
├── schemas/implementation/    # 구현팀 input/output schema
├── prompts/implementation/    # Agent별 prompt
├── orchestrator/              # 순차 실행 파이프라인
├── outputs/                   # 산출물, 실행 로그, QA 결과
├── main.py                    # active orchestrator entrypoint
└── app.py                     # quiz_contents.json 기반 Streamlit MVP
```

## 설치 방법

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
```

## `.env` 사용

실제 키는 `.env`에 두는 편이 좋다. 저장소에는 [.env.example](.env.example)만 추적하고, `.env`는 `.gitignore`로 제외한다.

```bash
cp .env.example .env
```

## 환경변수

runtime 실행은 provider-priority LLM client를 사용한다.

우선순위는 아래와 같다.

1. Gemini API (`GEMINI_API_KEY`)
2. Upstage API (`UPSTAGE_API_KEY`)

앞선 provider가 실패하면 다음 provider로 자동 failover 한다.

### Gemini 예시

```bash
export GEMINI_API_KEY="..."
export GEMINI_MODEL="gemini-3.1-pro"  # internal alias -> gemini-3.1-pro-preview
export GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta"  # optional
```

runtime 기본 경로에서는 일반 OpenAI-compatible provider를 더 이상 사용하지 않는다.
Upstage는 내부적으로 OpenAI-compatible API 형식을 사용하지만, runtime 우선순위에서는
명시적으로 `2순위 Upstage`로 취급한다.

### Upstage Solar Pro2 예시

`UPSTAGE_API_KEY`가 있으면 Upstage가 3순위 fallback provider로 추가된다.

```bash
export UPSTAGE_API_KEY="..."
export UPSTAGE_MODEL="solar-pro2"
export UPSTAGE_BASE_URL="https://api.upstage.ai/v1"  # optional
```

`UPSTAGE_MODEL`을 생략하면 기본값으로 `solar-pro2`를 사용한다. 계정에서 다른 모델 slug를 써야 하면 그 값을 그대로 넣으면 된다.
`main.py`는 실행 시 루트의 `.env` 파일이 있으면 자동으로 읽는다.

### 일반 OpenAI-compatible 예시

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"  # optional
```

## 파이프라인 실행 방법

```bash
.venv/bin/python main.py
```

옵션 예시:

```bash
.venv/bin/python main.py --input-path inputs/quiz_service_spec.md --output-dir outputs
```

`target_framework`의 기본값은 `streamlit`이다. 현재 Prototype Builder가 실제로
생성하는 앱은 Streamlit `app.py`뿐이며, `react`, `fastapi`, `nextjs` 같은 값은
명확한 unsupported 결과와 로그를 남기고 local checks 전에 중단한다.

## Outputs 확인 방법

실행이 끝나면 `outputs/` 아래에 아래 파일이 생성된다.

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

`quiz_contents.json`의 현재 계약은 다음과 같다.

- `quiz_type`: 상호작용 유형
  - `더 좋은 질문 고르기`
  - `질문에서 빠진 요소 찾기`
  - `모호한 질문 고치기`
  - `상황에 맞는 질문 만들기`
- `learning_dimension`: 학습 차원
  - `구체성`
  - `맥락성`
  - `목적성`
  - `종합성`

## Streamlit MVP 실행 방법

`app.py`는 `outputs/quiz_contents.json`을 읽는 최소 퀴즈 MVP다.

먼저 파이프라인으로 콘텐츠를 생성한 뒤 실행한다.

```bash
.venv/bin/python -m streamlit run app.py
```

화면에서 확인할 수 있는 핵심 흐름은 다음과 같다.

1. 생성된 8개 문제 확인
2. 객관식 답안 선택
3. 채점 결과 확인
4. 정답, 해설, 학습 포인트 확인

## 테스트

자동 테스트는 실제 LLM API를 호출하지 않는다.
`tests/` 아래 fake/mock LLM client를 사용해 deterministic하게 검증한다.

```bash
.venv/bin/python -m pytest
```

## 안정성 메모

현재 MVP 안정성을 위해 `Prototype Builder Agent / MVP 서비스 코드 생성 Agent`와
`QA & Alignment Agent / 최종 검수·정합성 확인 Agent`는 deterministic한 후처리 방식을 사용한다.
즉, 콘텐츠 생성은 live LLM으로 검증하되, `app.py` 템플릿 정규화와 QA summary는 검증된 계약을 우선 적용한다.

이 선택은 Streamlit MVP와 outputs 구조를 안정적으로 재현하기 위한 것이며,
후속 이슈에서는 builder/QA 단계까지 live generation 범위를 다시 확장할 수 있다.

## 구현 결정 기록

구현 중 기존 설계와 달라지는 판단은 아래에 기록한다.

- [docs/implementation_decisions.md](docs/implementation_decisions.md)
- `outputs/change_log.md`
