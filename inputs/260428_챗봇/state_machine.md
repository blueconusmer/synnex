# State Machine — 질문 코칭 챗봇

> **문서 성격**: 2차 산출물 (구현 명세서). 서비스의 각 상태와 상태 간 전이 조건, 예외 처리를 정의한 비즈니스 로직 문서.
> **작성 주체**: PM Agent
> **참조 문서**: constitution.md, data_schema.json
> **출처**: 김현아 님 기획서 v2 5.4.2 추출

---

## 1. 상태 목록

| 상태명 | 의미 | 대응 mode 값 |
| --- | --- | --- |
| `awaiting_input` | 사용자 질문 입력 대기 | — |
| `diagnosing` | AI가 루브릭 순차 판단 중 (내부 이동) | — |
| `need_specificity` | 구체성 부족 → 되묻기 필요 | `need_specificity` |
| `need_context` | 맥락성 부족 → 되묻기 필요 | `need_context` |
| `need_purpose` | 목적성 부족 → 되묻기 필요 | `need_purpose` |
| `completed` | 루브릭 최소 성취 기준 충족 → 결과 화면 전환 | `completed` |
| `error` | AI 응답 실패 또는 재시도 한도 초과 | — |

---

## 2. data_schema mode 값 매핑

| mode 값 | 반환 필드 |
| --- | --- |
| `need_specificity` | mode, diagnosis, follow_up_question, next_action |
| `need_context` | mode, diagnosis, follow_up_question, next_action |
| `need_purpose` | mode, diagnosis, follow_up_question, next_action |
| `completed` | mode, improved_question, next_action |
| — (내부 이동) | 반환 없음 |

---

## 3. 상태 전이 규칙

**평가 방식**: 순차 평가 (구체성 → 맥락성 → 목적성)

```
IF 사용자가 질문 제출
   → THEN 상태: diagnosing
   → 구체성 판단 시작

IF 구체성 양호 이상
   → THEN 상태: diagnosing
   → 맥락성 판단으로 이동

IF 구체성 미흡
   → THEN 상태: need_specificity
   → 출력:
       mode: "need_specificity"
       diagnosis: 구체성 보완을 유도하는 진단 문장
       follow_up_question: 구체성 보완을 유도하는 되묻기 질문
       next_action: "ask_more"

IF 맥락성 양호 이상
   → THEN 상태: diagnosing
   → 목적성 판단으로 이동

IF 맥락성 미흡
   → THEN 상태: need_context
   → 출력:
       mode: "need_context"
       diagnosis: 맥락성 보완을 유도하는 진단 문장
       follow_up_question: 맥락성 보완을 유도하는 되묻기 질문
       next_action: "ask_more"

IF 목적성 양호 이상
   → THEN 상태: completed
   → 출력:
       mode: "completed"
       improved_question: 루브릭 기준을 충족한 개선 질문
       next_action: "show_result"

IF 목적성 미흡
   → THEN 상태: need_purpose
   → 출력:
       mode: "need_purpose"
       diagnosis: 목적성 보완을 유도하는 진단 문장
       follow_up_question: 목적성 보완을 유도하는 되묻기 질문
       next_action: "ask_more"
```

---

## 4. 예외 처리 및 에러 메시지

```
IF turn_count >= 2 AND 기준 미충족
   → THEN 상태: completed (강제 전환)
   → 출력:
       mode: "completed"
       improved_question: 현재까지 입력을 바탕으로 생성한 최선의 개선 질문
       next_action: "show_result"
       message: "네 질문을 바탕으로 최선을 다해 도와줄게!"

IF AI 응답 오류 발생
   → THEN 상태: error
   → 출력:
       error: "ai_response_failed"
       message: "잠깐 문제가 생겼어. 다시 시도해줄래?"

IF 사용자 입력값 없음 (빈 문자열)
   → THEN 상태: awaiting_input 유지
   → 출력:
       message: "질문을 입력해줘야 도와줄 수 있어!"
```

---

## 5. 포함하지 않는 내용

- 실제 DB 상태 관리 로직 및 서버 내부 처리 방식은 포함하지 않는다.
- 구현 방법(코드 레벨)은 포함하지 않는다. 구현 방식은 Build Plan을 참조한다.
