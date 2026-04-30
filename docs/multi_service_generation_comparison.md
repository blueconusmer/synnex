# Multi-Service Generation Comparison

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

### 질문 코칭 챗봇

- 문제: 기존 deterministic loader/intake는 `content_types`, `total_count`, `screens`, `api_endpoints`, `content_distribution`를 채우지 못해 Input Intake에서 바로 `FAIL`로 중단됐다.
- 원인: 현재 generic 규칙이 비퀴즈 interaction service의 `data_schema.output.mode.allowed_values`, lower-case state names, interface screen labels, fenced endpoint 표기를 실행 계약 필드로 해석하지 못했다.
- 조치: `service_name` / `content_types` / `total_count` / `screens` / `api_endpoints` / `content_distribution` 추출을 deterministic fallback으로 일반화했고, `mode.allowed_values` 기반 `total_count`는 자동 확정하지 않고 `NEEDS_PLANNING_REVIEW` + warn-and-continue로 처리했다.
- 결과: 챗봇 입력은 더 이상 intake에서 막히지 않고 `Spec Intake`, `Requirement Mapping`까지 진행한다. 현재 다음 병목은 `Content & Interaction`의 quiz semantic validator이며, 첫 실패는 `Semantic validator failed after regeneration for item QC004`로 재현된다.
