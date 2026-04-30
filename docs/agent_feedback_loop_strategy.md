# Agent Feedback Loop Strategy

## 목적

이 문서는 현재 6-Agent 순차 파이프라인 위에 추가되는 **앞단 3-Agent feedback loop prototype**의 기준을 정리한다.

이번 범위의 목표는 전체 오케스트레이터를 만드는 것이 아니라, 아래 가설을 검증할 수 있는 최소 구조를 구현하는 것이다.

- LLM 기반 `app.py` 생성 불안정의 주요 원인은 Builder 자체만이 아니라, 앞단 명세 해석과 전달 계약 부족일 수 있다.

따라서 이번 loop는 아래 3개 Agent만 retry target으로 삼는다.

1. `Spec Intake Agent / 구현 명세서 분석 Agent`
2. `Requirement Mapping Agent / 구현 요구사항 정리 Agent`
3. `Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent`

`Prototype Builder`, `Run Test And Fix`, `QA & Alignment`는 이번 범위에서 **observation source**다. 이 단계들은 관찰 신호를 제공하지만 retry target은 아니다.

## 현재 파이프라인과 reflection 범위

현재 active 파이프라인은 순차 실행형이다.

`Input Intake → Spec Intake → Requirement Mapping → Content & Interaction → Prototype Builder → Run Test And Fix → QA & Alignment`

이미 존재하는 reflection은 Builder/Test 구간에 한정된다.

- LLM app.py 생성
- local check
- 최소 patch 1회
- 필요 시 fallback template

이번 문서에서 정의하는 loop는 이 reflection을 대체하지 않는다. 대신 그 이후에도 Builder 결과가 앞단 산출물 해석 문제로 보일 때, **앞단 3-Agent 중 하나로 되돌리는 기준**을 추가한다.

## 왜 전체 orchestrator가 아닌가

이번 단계에서 전체 orchestrator를 구현하지 않는 이유는 다음과 같다.

- 현재 가장 큰 불안정성은 Builder 이후가 아니라 Builder가 읽는 명세 계약의 일관성 부족과 연결되어 있다.
- 전체 multi-agent loop를 한 번에 구현하면 범위가 과도하게 커진다.
- 앞단 산출물 계약만 정리해도 Builder 성공률 개선 효과를 관찰할 수 있다.

따라서 이번 loop는 **명세 해석 보강 prototype**으로 제한한다.

## 앞단 3-Agent 산출물 계약

### Spec Intake

다음 단계가 기대하는 핵심 계약:

- `service_summary`가 구현 대상 서비스를 한 문단 수준으로 설명한다.
- `normalized_requirements`가 비어 있지 않다.
- `delivery_expectations`, `acceptance_focus`가 downstream 기준으로 재사용 가능하다.

### Requirement Mapping

다음 단계가 기대하는 핵심 계약:

- `implementation_targets`가 실제 구현 작업 단위를 설명한다.
- `file_plan`이 outputs/app/QA 산출물과 연결된다.
- `app_constraints`가 Builder가 읽을 수 있는 app-level 제약을 담는다.
- `test_strategy`가 local checks 기대치를 반영한다.

### Content & Interaction

다음 단계가 기대하는 핵심 계약:

- `interaction_units`가 primary contract다.
- `interaction_units`는 `unit_id`, `interaction_type`, `next_step`, `metadata`를 포함한다.
- `interaction_validation.structure_valid`가 `true`여야 한다.
- quiz 성격의 서비스라면 legacy `QuizItem` 하위 호환도 유지한다.
- `evaluation_rules`는 점수/피드백/완료 조건을 담아야 한다.

## Builder/Runtime/QA가 앞단 산출물에서 기대하는 조건

Builder가 앞단에서 기대하는 최소 신호:

- 서비스 요약이 너무 추상적이지 않을 것
- 구현 제약과 화면/상태 흐름 단서가 app constraints에 포함될 것
- `interaction_units`가 실제 사용자 흐름을 표현할 것
- `evaluation_rules`가 결과 처리 규칙을 전달할 것

Runtime/QA가 앞단에서 기대하는 최소 신호:

- app 생성 prompt가 읽을 수 있는 state/result/battle/feedback 흐름 단서
- interaction 구조와 content distribution의 정합성
- 서비스 목적과 생성 결과의 alignment

## Feedback Signal 분류

이번 prototype에서는 다음 issue type을 사용한다.

- `SPEC_INTERPRETATION_ISSUE`
- `REQUIREMENT_MAPPING_ISSUE`
- `CONTENT_INTERACTION_ISSUE`
- `APP_GENERATION_FEEDBACK`
- `AMBIGUOUS_ISSUE`
- `NONE`

또한 code-only runtime failure는 retry target이 아니다.

- pure syntax error
- import typo
- Streamlit API typo
- patch로 바로 고칠 수 있는 소규모 code-only bug

이 경우는 `OUT_OF_SCOPE`로 기록하고 기존 Builder/Test 영역으로 남긴다.

## Rule-based 라우팅 기준

기본 라우팅은 rule-based다.

### Spec Intake로 되돌리는 경우

- `service_summary`가 비어 있거나 지나치게 짧다
- `normalized_requirements`가 비어 있다
- downstream에서 구현 의도 자체를 읽기 어려운 수준이다

### Requirement Mapping으로 되돌리는 경우

- `implementation_targets`가 비어 있다
- `app_constraints`가 비어 있거나 Builder가 읽기 어려운 수준이다
- app-level 제약이 요구사항 계약으로 충분히 번역되지 않았다

### Content & Interaction으로 되돌리는 경우

- `interaction_units`가 비어 있다
- `interaction_validation.structure_valid = false`
- `next_step` 또는 interaction shape가 downstream에서 쓰기 어렵다
- `evaluation_rules`가 부족하다

### Ambiguous / App Generation Feedback

Builder fallback 또는 QA mismatch가 있었지만, 위 3개 target 중 하나로 확정하기 어려우면:

- 먼저 `APP_GENERATION_FEEDBACK`로 기록한다
- candidate agent를 2개 이상 남긴다
- 그 다음에만 LLM judge를 호출한다

## LLM Judge 호출 조건

LLM judge는 **기본 라우터가 아니다**.

아래 조건일 때만 호출한다.

- rule-based가 candidate agent를 2개 이상 남겼다
- 또는 issue는 있는데 target agent를 1개로 축소하지 못했다

LLM judge의 역할:

- ambiguous case에서 target agent를 하나 고른다
- retry instruction을 구조화해서 만든다

LLM judge의 비역할:

- 직접 산출물을 수정하지 않는다
- Agent 간 실제 대화를 수행하지 않는다
- Builder/Run Test를 retry target으로 선택하지 않는다

## Retry 정책과 중단 조건

이번 prototype의 retry 정책은 다음과 같다.

- 최대 retry 횟수: `3`
- 동일 agent 연속 retry 최대: `2`
- 매 cycle에서 retry target은 **1개 agent만**
- rerun 범위는 target agent 이후 downstream 전체

중단 조건:

- `retry_required = false`
- 동일 agent가 연속 2회 target이 되었는데도 동일 issue가 반복
- 총 retry 3회 도달
- LLM judge 실패 또는 invalid output

이 경우 최종 상태는 `NEEDS_HUMAN_REVIEW` 또는 `OUT_OF_SCOPE`가 된다.

## Human Review 기준

다음 상황은 사람 검토로 넘긴다.

- ambiguous case에서 judge도 target을 확정하지 못함
- 동일 agent로 두 번 되돌렸는데 동일 문제가 반복됨
- retry budget 3회를 모두 사용했는데 해결되지 않음
- code-only runtime failure처럼 앞단 retry로 해결할 문제가 아님

## 개발팀장 Agent에 대한 입장

개발팀장 Agent는 장기적으로 유효할 수 있다. 그러나 이번 구현 범위는 아니다.

이번 prototype은 아래 원칙을 따른다.

- 기본 라우팅은 rule-based
- 애매할 때만 LLM judge
- 실제 retry target은 앞단 3-Agent만

즉, 지금 단계에서는 “상위 감독 Agent”보다 **설명 가능한 라우팅 기준과 재실행 근거**가 더 중요하다.

## Hybrid 접근의 장단점

장점:

- 명확한 케이스는 추적 가능하게 처리할 수 있다
- 애매한 케이스만 LLM에 맡겨 비용과 불확실성을 줄인다
- Builder 실패 원인을 앞단 명세 관점에서 다시 볼 수 있다

한계:

- 앞단 명세 보강만으로 해결되지 않는 Builder 문제는 여전히 남는다
- rule-based 기준이 너무 약하면 human review가 늘어날 수 있다
- LLM judge도 완전한 원인 판별기는 아니다

## 이번 prototype의 산출물

이번 구현에서 새로 남기는 핵심 산출물은 다음과 같다.

- `orchestration_decision.json`
- `retry_history.json`

또한 아래 파일에도 loop 요약이 추가된다.

- `qa_report.md`
- `final_summary.md`
- `change_log.md`
