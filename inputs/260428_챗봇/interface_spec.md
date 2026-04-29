# Interface Spec — 질문 코칭 챗봇

> **문서 성격**: 2차 산출물 (구현 명세서). 화면, API, 모듈 간의 입출력 연결 기준을 정의한 문서로, 프론트엔드와 백엔드가 협업하기 위한 계약서.
> **작성 주체**: PM Agent
> **참조 문서**: constitution.md, data_schema.json, state_machine.md
> **의존 관계**: data_schema_write, state_machine_write 완료 후 작성 시작
> **출처**: 김현아 님 기획서 v2 5.4.4 추출

---

## 1. API 명세

### 1.1. Endpoint 정의

```
POST /api/chat
- 설명: 사용자 질문을 AI에 전달하고 루브릭 판단 결과를 반환한다.
- 인증: 없음 (MVP 기준)
- Content-Type: application/json
```

### 1.2. Request / Response 정의

**[Request]**

```json
{
  "user_question": "string",
  "session_id": "string",
  "turn_count": "number"
}
```

**[Response — 정상]**

```json
{
  "mode": "need_specificity / need_context / need_purpose / completed",
  "diagnosis": "string",
  "follow_up_question": "string / null",
  "improved_question": "string / null",
  "next_action": "ask_more / show_result"
}
```

### 1.3. 에러 응답 정의

**[Response — 에러]**

```
HTTP 500
```

```json
{
  "error": "ai_response_failed",
  "message": "잠깐 문제가 생겼어. 다시 시도해줄래?"
}
```

---

## 2. UI 인터랙션 정의

### 2.1. 화면별 동작 기준

**질문 입력 화면**

- 사용자가 텍스트 입력창에 질문을 작성하고 제출 버튼을 누른다.
- 제출 버튼 클릭 → POST `/api/chat` 요청 (`user_question`, `session_id`, `turn_count`)
- 요청 중 로딩 인디케이터 표시
- 빈 문자열 제출 시 → API 요청 없이 "질문을 입력해줘야 도와줄 수 있어!" 메시지 표시

**되묻기 화면 (mode: `need_specificity` / `need_context` / `need_purpose`)**

- `diagnosis` 말풍선 출력
- `follow_up_question` 말풍선 출력
- 재입력창 활성화 → 사용자가 보완된 질문 재제출 가능
- `turn_count` +1 후 POST `/api/chat`

**재요청 결과 화면 (mode: `completed`)**

- `original_question` vs `improved_question` 비교 출력
- 칭찬 피드백 메시지 출력
- 다시 시도 버튼 클릭 → 질문 입력 화면으로 초기화

### 2.2. mode별 렌더링 규칙

| mode 값 | 프론트 처리 | 표시 요소 |
| --- | --- | --- |
| `need_specificity` | 되묻기 화면 유지 | diagnosis + follow_up_question 말풍선 출력 / 재입력창 활성화 / improved_question 무시 |
| `need_context` | 되묻기 화면 유지 | diagnosis + follow_up_question 말풍선 출력 / 재입력창 활성화 / improved_question 무시 |
| `need_purpose` | 되묻기 화면 유지 | diagnosis + follow_up_question 말풍선 출력 / 재입력창 활성화 / improved_question 무시 |
| `completed` | 결과 화면으로 전환 | original_question vs improved_question 비교 출력 / 칭찬 피드백 출력 / 다시 시도 버튼 활성화 |
| 에러 | 현재 화면 유지 | 에러 메시지 말풍선 출력 / 재시도 버튼 활성화 |

---

## 3. 모듈 간 연결 구조

```
[사용자 질문 입력]
         ↓ 제출 버튼 클릭
[프론트엔드] → POST /api/chat
         ↓
[백엔드] → AI API 호출 (prompt_spec 적용)
         ↓
[AI] → 루브릭 순차 판단 → mode 결정
         ↓
[백엔드] → Response 반환
         ↓
[프론트엔드] → mode에 따라 화면 분기 렌더링
```
