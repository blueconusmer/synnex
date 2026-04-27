# Interface Spec — 질문력 강화 퀘스트 서비스 인터페이스 명세

> **문서 성격**: 2차 산출물 (구현 명세서). User Flow와 data_schema를 기반으로 작성된 화면·API 명세.
> **참조 문서**: state_machine.md, data_schema.json
> **버전**: v0.1 (Layer 2 구축용 mock 데이터)

---

## 1. 화면 구성 개요

본 서비스는 5개 화면으로 구성된다.

| 화면 ID | 화면명 | 대응 상태 |
| --- | --- | --- |
| `S0` | 시작 화면 | SESSION_START |
| `S1` | 객관식 퀘스트 화면 | QUEST_1_ACTIVE |
| `S2` | 객관식 결과 화면 | QUEST_1_FEEDBACK |
| `S3` | 개선형 퀘스트 화면 | QUEST_2_ACTIVE / QUEST_3_ACTIVE |
| `S4` | 개선형 결과 화면 | QUEST_2_FEEDBACK / QUEST_3_FEEDBACK |
| `S5` | 세션 결과 화면 | SESSION_COMPLETED |

---

## 2. 화면별 구성 요소 및 인터랙션

### 2.1. `S0` 시작 화면

| 요소 | 내용 |
| --- | --- |
| 헤더 | "오늘의 질문력 퀘스트" |
| 설명 텍스트 | "3개의 퀘스트를 풀고 질문력 점수를 쌓아보세요!" |
| 현재 등급 표시 | 사용자의 current_grade (없으면 "브론즈") |
| 누적 점수 표시 | 사용자의 cumulative_score (없으면 0점) |
| 시작 버튼 | "세션 시작" |

**인터랙션**: 시작 버튼 클릭 → POST `/api/session/start` 호출 → 응답 수신 → S1으로 전환

---

### 2.2. `S1` 객관식 퀘스트 화면

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "퀘스트 1 / 3" |
| 퀘스트 유형 라벨 | "더 좋은 질문 고르기" |
| 학습 맥락 표시 | quest.topic_context (예: "국어 비유 표현 학습") |
| 원본 질문 표시 | quest.original_question (모호한 질문 예시) |
| 안내 문구 | "이 질문을 더 좋게 바꾼 선택지는 무엇일까요?" |
| 선택지 4개 | quest.options (라디오 버튼 형식) |
| 제출 버튼 | "제출" (선택지 미선택 시 비활성화) |

**인터랙션**: 선택지 1개 선택 후 제출 버튼 클릭 → POST `/api/quest/submit` 호출 → 응답 수신 → S2로 전환

**예외**: 선택지 미선택 상태로 제출 시도 → "선택지를 골라주세요" 인라인 메시지 표시

---

### 2.3. `S2` 객관식 결과 화면

| 요소 | 내용 |
| --- | --- |
| 결과 헤더 | is_correct = true → "정답입니다!" / false → "이 질문도 좋아요" |
| 사용자 선택 표시 | 선택했던 선택지 텍스트 |
| 정답 표시 | quest.options[correct_option_index] |
| 해설 영역 | evaluation.feedback (왜 정답이 가장 좋은 질문인지) |
| 획득 점수 표시 | "+{earned_score}점" |
| 다음 버튼 | "다음 퀘스트로" |

**인터랙션**: 다음 버튼 클릭 → S3으로 전환 (퀘스트 2 로드)

---

### 2.4. `S3` 개선형 퀘스트 화면

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "퀘스트 2 / 3" 또는 "퀘스트 3 / 3" |
| 퀘스트 유형 라벨 | "질문 더 좋게 만들기" |
| 학습 맥락 표시 | quest.topic_context |
| 원본 질문 표시 | quest.original_question |
| 안내 문구 | "이 질문을 더 명확하게 바꿔보세요. 무엇을, 왜, 어떻게가 들어가면 좋아요." |
| 입력창 | 텍스트 영역 (최소 10자, 최대 300자) |
| 글자 수 표시 | "{현재 글자 수} / 300" |
| 제출 버튼 | "제출" (10자 미만 시 비활성화) |

**인터랙션**: 텍스트 입력 후 제출 버튼 클릭 → POST `/api/quest/submit` 호출 → 응답 수신 → S4로 전환

**예외 처리**:
- 빈 텍스트 제출 시도 → "질문을 작성해주세요"
- 10자 미만 제출 시도 → "조금 더 자세히 작성해주세요 (최소 10자)"

---

### 2.5. `S4` 개선형 결과 화면

| 요소 | 내용 |
| --- | --- |
| 결과 헤더 | overall에 따라 분기:<br>excellent → "아주 명확해졌어요!"<br>good → "좋아졌어요!"<br>needs_work → "한 부분만 더 보완해볼까요?" |
| Before / After 비교 | 원본 질문 → 사용자 작성 질문 (시각적 비교) |
| 루브릭 결과 | 구체성 / 맥락성 / 목적성 각각 우수·양호·미흡 뱃지 |
| 피드백 영역 | evaluation.feedback (한두 문장) |
| 획득 점수 표시 | "+{earned_score}점" |
| 다음 버튼 | "다음 퀘스트로" 또는 마지막 퀘스트면 "결과 보기" |

**인터랙션**: 다음 버튼 클릭 → 퀘스트 2 결과면 S3 (퀘스트 3 로드), 퀘스트 3 결과면 S5로 전환

---

### 2.6. `S5` 세션 결과 화면

| 요소 | 내용 |
| --- | --- |
| 결과 헤더 | "오늘의 퀘스트 완료!" |
| 이번 세션 점수 | "이번 세션: +{session_score}점" |
| 누적 총점 표시 | "전체 누적: {cumulative_score}점" |
| 현재 등급 표시 | "현재 등급: {current_grade}" (등급에 맞는 시각적 뱃지) |
| 등급 상승 메시지 | grade_up_event = true 시: "축하해요! 이제 {new_grade} 단계예요" (애니메이션 포함) |
| 재시작 버튼 | "새 세션 시작" |
| 종료 버튼 | "종료" |

**인터랙션**:
- "새 세션 시작" 클릭 → S0으로 이동
- "종료" 클릭 → 메인 화면 또는 종료

---

## 3. API 명세

### 3.1. 세션 시작

**Endpoint**: `POST /api/session/start`

**Request**:
```json
{
  "user_id": "string"
}
```

**Response**:
```json
{
  "session_id": "string",
  "quests": [
    {
      "quest_id": "string",
      "quest_type": "multiple_choice",
      "difficulty": "intro",
      "topic_context": "string",
      "original_question": "string",
      "options": ["string", "string", "string", "string"]
    },
    {
      "quest_id": "string",
      "quest_type": "question_improvement",
      "difficulty": "main",
      "topic_context": "string",
      "original_question": "string"
    },
    {
      "quest_id": "string",
      "quest_type": "question_improvement",
      "difficulty": "main",
      "topic_context": "string",
      "original_question": "string"
    }
  ],
  "user_progress": {
    "cumulative_score": 0,
    "current_grade": "bronze",
    "completed_session_count": 0
  }
}
```

**Notes**:
- 응답에는 정답·해설이 포함되지 않는다 (`correct_option_index`, `explanation`은 서버 보관).
- 3개 퀘스트는 [intro 1, main 2] 순서로 고정 반환.

---

### 3.2. 퀘스트 답변 제출

**Endpoint**: `POST /api/quest/submit`

**Request (객관식)**:
```json
{
  "session_id": "string",
  "quest_id": "string",
  "user_response": 1
}
```

**Request (개선형)**:
```json
{
  "session_id": "string",
  "quest_id": "string",
  "user_response": "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해줘"
}
```

**Response (객관식)**:
```json
{
  "answer_id": "string",
  "evaluation": {
    "evaluation_type": "correctness",
    "is_correct": true,
    "feedback": "정답입니다! 이 선택지가 가장 좋아요. ..."
  },
  "earned_score": 20,
  "correct_option_index": 1,
  "is_session_complete": false
}
```

**Response (개선형)**:
```json
{
  "answer_id": "string",
  "evaluation": {
    "evaluation_type": "rubric",
    "rubric_result": {
      "specificity": "excellent",
      "context": "excellent",
      "purpose": "excellent",
      "overall": "excellent"
    },
    "feedback": "질문이 아주 명확해졌어요! 무엇을, 왜, 어떻게가 모두 잘 드러나 있어요."
  },
  "earned_score": 30,
  "is_session_complete": false
}
```

**Notes**:
- `is_session_complete`가 true면 클라이언트는 다음 호출로 `/api/session/result`를 호출한다.
- 마지막 퀘스트(3번째) 제출 시 `is_session_complete = true`.

---

### 3.3. 세션 결과 조회

**Endpoint**: `GET /api/session/result?session_id={session_id}`

**Response**:
```json
{
  "session_id": "string",
  "session_score": 70,
  "user_progress": {
    "cumulative_score": 170,
    "current_grade": "silver",
    "completed_session_count": 3
  },
  "grade_up_event": true,
  "previous_grade": "bronze",
  "new_grade": "silver"
}
```

---

## 4. 에러 응답 공통 형식

```json
{
  "error_code": "E_LLM_TIMEOUT",
  "error_message": "잠시 후 다시 시도해주세요"
}
```

| HTTP Status | 발생 조건 |
| --- | --- |
| 400 | 요청 형식 오류 (E_NO_SELECTION, E_EMPTY_INPUT, E_TOO_SHORT) |
| 500 | 서버 내부 오류 (E_LLM_TIMEOUT, E_LLM_INVALID_RESPONSE, E_QUEST_LOAD_FAIL) |

---

## 5. 인터랙션 보장 사항

본 인터페이스 명세는 다음을 보장한다.

1. 사용자는 한 화면당 한 가지 액션만 수행한다 (선택 또는 입력 또는 다음 버튼).
2. 모든 화면은 진행률(현재 퀘스트 / 전체 퀘스트)을 표시한다.
3. 정답·해설 정보는 클라이언트가 미리 알 수 없도록 서버에서만 보관·처리한다.
4. LLM 평가 응답은 항상 정해진 JSON 스키마를 따르며, 실패 시 사용자에게 재시도 안내가 표시된다.
5. 세션 결과 화면에 표시되는 누적 점수와 등급은 서버 응답값을 그대로 반영한다 (클라이언트 계산 금지).
