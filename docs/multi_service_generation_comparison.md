# Multi-Service Generation Comparison

## 질문력 강화 퀘스트 v2

- 범위: `inputs/260429_퀘스트_v2/` 기준선 검증 1차
- 제외: `inputs/260428_챗봇/` 비교 및 전용 loader/validator 보완

### 결과 요약

- Input Intake: `AUTO_FIXED`
- target_framework: `streamlit`
- interaction_mode: `quiz`
- interaction_mode_reason: `quiz markers detected: 정답, 점수, 배틀, quest, multiple_choice`
- interaction_units: `12`
- interaction_validation.structure_valid: `true`
- QuizItem 하위 호환: 유지
- app.py 생성: `outputs/question_quest_v2/app.py`
- Streamlit smoke: `PASS`
- fallback template 사용: `YES`
- fallback_reason: `LLM_OUTPUT_INVALID: app_source must include state-machine marker: current_screen.`
- feedback loop 최종 상태: `NEEDS_HUMAN_REVIEW`

## 질문 코칭 챗봇

- 범위: `inputs/260428_챗봇/` deterministic generic loader/intake 확장 이후 기준선 검증
- 원칙: 챗봇 전용 loader, builder, runtime 로직 없이 generic pipeline만 사용

### 결과 요약

- Input Intake: `NEEDS_PLANNING_REVIEW`
- target_framework: `streamlit`
- service_name: `Question Coaching Chatbot`
- content_types: `need_specificity`, `need_context`, `need_purpose`, `completed`
- total_count: `4` (source: `mode.allowed_values` count, planning review required)
- content_distribution: 각 type당 `1`
- Pipeline 진행: `Spec Intake PASS` → `Requirement Mapping PASS` → `Content & Interaction FAIL`
- 첫 downstream 실패 stage: `Content & Interaction`
- Builder / app.py 생성: `NOT RUN`

## Debugging Notes

### 질문력 강화 퀘스트 v2

- 문제: `Session.quest_sequence` 기반 분포가 `multiple_choice 1 + situation_card 1 + question_improvement 1 + battle 1`로 잘못 추론되어 Input Intake가 `FAIL`로 떨어졌고, 이후 Builder 단계에서는 state-machine marker 부족으로 fallback template이 반복 사용됐다.
- 원인: `situation_card_advanced`가 `situation_card`로 정규화되지 않아 `content_distribution` 합계가 `4`로 계산됐고, v2 입력의 flow/state 요구가 Builder가 기대하는 marker 수준으로 충분히 전달되지 않았다.
- 조치: loader/validator에서 `quest_sequence`, lower-case state names, endpoint 표기, `###` 하위 섹션을 읽도록 보완했고, `situation_card_advanced -> situation_card` alias를 추가해 `1/2/1/1` 분포를 안정적으로 추론하게 수정했다. 또한 fallback app이 5퀘스트 + battle + 점수/등급 요약을 반영하도록 보강하고, v2 baseline 테스트를 추가했다.
- 결과: Input Intake는 `AUTO_FIXED`로 통과했고, `outputs/question_quest_v2/` 산출물과 `app.py`가 생성되며 `streamlit_smoke`까지 통과했다. 다만 full run 기준 최종 상태는 `NEEDS_HUMAN_REVIEW`이며, fallback template 사용은 계속 기록된다.

### 남은 한계

- LLM-generated `app.py`는 이번 기준선에서도 `current_screen` 등 state-machine marker 계약을 끝까지 만족하지 못해 fallback template이 최종 사용되었다.
- `#40`의 upstream feedback loop는 실제로 3회까지 개입했지만, Builder fallback 문제를 해소하지 못해 최종 `NEEDS_HUMAN_REVIEW`로 종료되었다.
- 챗봇 입력(`inputs/260428_챗봇/`) 비교는 이번 문서 범위에 포함하지 않는다.

### 질문 코칭 챗봇

- 문제: 기존 deterministic loader/intake는 `content_types`, `total_count`, `screens`, `api_endpoints`, `content_distribution`를 채우지 못해 Input Intake에서 바로 `FAIL`로 중단됐다.
- 원인: 현재 generic 규칙이 비퀴즈 interaction service의 `data_schema.output.mode.allowed_values`, lower-case state names, interface screen labels, fenced endpoint 표기를 실행 계약 필드로 해석하지 못했다.
- 조치: `service_name` / `content_types` / `total_count` / `screens` / `api_endpoints` / `content_distribution` 추출을 deterministic fallback으로 일반화했고, `mode.allowed_values` 기반 `total_count`는 자동 확정하지 않고 `NEEDS_PLANNING_REVIEW` + warn-and-continue로 처리했다.
- 결과: 챗봇 입력은 더 이상 intake에서 막히지 않고 `Spec Intake`, `Requirement Mapping`까지 진행한다. 현재 다음 병목은 `Content & Interaction`의 quiz semantic validator이며, 첫 실패는 `Semantic validator failed after regeneration for item QC004`로 재현된다.
