# Interface Spec — 질문력 강화 퀘스트 서비스

> **문서 성격**: 2차 산출물 (구현 명세서). 화면, API, 모듈 간의 입출력 연결 기준을 정의한 문서.
> **작성 주체**: PM Agent
> **참조 문서**: constitution.md, data_schema.json, state_machine.md
> **의존 관계**: data_schema.json, state_machine.md 완료 후 작성
> **버전**: v2.0

---

## 1. 화면 구성 개요

| 화면 ID | 화면명 | 대응 상태 |
| --- | --- | --- |
| `S0` | 시작 화면 | session_start |
| `S1` | Q1 객관식 퀘스트 | quest_active (multiple_choice) |
| `S2` | Q1 결과 화면 | quest_feedback (Q1) |
| `S3` | Q2·Q3·Q4 작성형 퀘스트 | quest_active (situation_card / question_improvement) |
| `S4` | Q2·Q3·Q4 결과 화면 | quest_feedback (Q2~Q4) |
| `S5` | Q5 배틀 라운드 진행 | battle_round_active |
| `S6` | Q5 배틀 라운드 결과 | battle_round_feedback |
| `S7` | Q5 배틀 최종 결과 | battle_completed |
| `S8` | 세션 완료 화면 | session_completed |

---

## 2. 화면별 구성 요소 및 인터랙션

### S0. 시작 화면

| 요소 | 내용 |
| --- | --- |
| 헤더 | "오늘의 질문력 퀘스트" |
| 현재 등급·누적 점수 | user_progress.current_grade / cumulative_score |
| 세션 구성 안내 | "Q1 객관식 → Q2 상황카드 → Q3 개선형 → Q4 상황카드 심화 → Q5 배틀 3라운드" |
| 시작 버튼 | "세션 시작" |

**인터랙션**: 시작 버튼 → `POST /api/session/start` → S1

---

### S1. Q1 객관식 퀘스트

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "퀘스트 1 / 5" |
| 유형 라벨 | "좋은 질문 고르기" |
| 학습 맥락 | quest.topic_context |
| 안내 문구 | "다음 중 AI에게 가장 잘 물어본 질문은 무엇일까요?" |
| 선택지 4개 | quest.options (라디오 버튼) |
| 제출 버튼 | "제출" (미선택 시 비활성) |

**인터랙션**: 선택지 선택 → 제출 → `POST /api/quest/submit` → S2

---

### S2. Q1 결과 화면

| 요소 | 내용 |
| --- | --- |
| 결과 헤더 | is_correct=true → "정답이에요!" / false → "이 선택도 좋아요" |
| 정답 표시 | options[correct_option_index] |
| 해설 | evaluation.feedback |
| 획득 점수 | "+{earned_score}점" |
| 다음 버튼 | "다음 퀘스트로" |

**인터랙션**: 다음 버튼 → S3 (Q2 로드)

---

### S3. Q2·Q3·Q4 작성형 퀘스트

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "퀘스트 {n} / 5" |
| 유형 라벨 | situation_card → "상황 카드" / question_improvement → "질문 개선하기" |
| 상황 카드 (situation_card) | quest.situation |
| 원본 질문 (question_improvement) | quest.original_question |
| 안내 문구 | situation_card → "이 상황에서 AI에게 어떻게 질문하시겠습니까? 주제·상황·원하는 답을 넣어보세요." / question_improvement → "이 질문을 더 명확하게 바꿔보세요." |
| 입력창 | 텍스트 영역 (최소 10자, 최대 300자) |
| 글자 수 | "{현재} / 300" |
| 제출 버튼 | "제출" (10자 미만 시 비활성) |

**인터랙션**: 작성 → 제출 → `POST /api/quest/submit` → S4

---

### S4. Q2·Q3·Q4 결과 화면

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "퀘스트 {n} / 5 완료" |
| 결과 헤더 | excellent → "아주 명확해졌어요!" / good → "좋아졌어요!" / needs_work → "한 부분만 더 보완해볼까요?" |
| 루브릭 결과 | 구체성 / 맥락성 / 목적성 각각 우수·양호·미흡 뱃지 |
| 피드백 | evaluation.feedback |
| 획득 점수 | "+{earned_score}점" |
| 콤보 표시 | combo_count >= 2 → "🔥 {combo_count}콤보!" |
| 다음 버튼 | "다음 퀘스트로" (Q4이면 "배틀 시작!") |

**인터랙션**: 다음 버튼 → S3 또는 S5 (Q5 배틀)

---

### S5. Q5 배틀 라운드 진행

| 요소 | 내용 |
| --- | --- |
| 진행 표시 | "배틀 라운드 {round_number} / 3" |
| 승리 현황 | "나 {user_wins}승 vs AI {ai_wins}승" |
| 상황 카드 | 해당 라운드의 situation |
| 안내 문구 | "AI보다 더 좋은 질문을 만들어보세요!" |
| 입력창 | 텍스트 영역 (최소 10자, 최대 300자) |
| 제출 버튼 | "제출" |

**인터랙션**: 작성 → 제출 → `POST /api/battle/submit` → S6

---

### S6. Q5 배틀 라운드 결과

| 요소 | 내용 |
| --- | --- |
| 라운드 결과 헤더 | round_winner=user → "이겼어요!" / ai → "이번엔 AI가 더 잘했어요" / 무승부 → "아쉽게 비겼어요" |
| 비교 표 | 내 질문 vs AI 질문 / 구체성·맥락성·목적성 비교 뱃지 / 합산 점수 |
| 획득 점수 | "+{earned_score}점" |
| 승리 현황 | "나 {user_wins}승 vs AI {ai_wins}승" |
| 다음 버튼 | 배틀 미완료 → "다음 라운드" / 완료 → "최종 결과 보기" |

**인터랙션**: 다음 버튼 → S5 또는 S7

---

### S7. Q5 배틀 최종 결과

| 요소 | 내용 |
| --- | --- |
| 최종 결과 헤더 | user_won → "AI를 이겼어요!" / ai_won → "다음엔 이길 수 있어요!" |
| 퍼펙트 배너 | is_perfect=true → "퍼펙트 클리어!" |
| 최종 스코어 | "{user_wins}승 vs {ai_wins}승" |
| 배틀 보너스 | "+{battle_bonus}점" |
| 결과 보기 버튼 | "세션 결과 보기" |

**인터랙션**: 결과 보기 → `GET /api/session/result` → S8

---

### S8. 세션 완료 화면

| 요소 | 내용 |
| --- | --- |
| 헤더 | "세션 완료!" |
| 이번 세션 획득 점수 | "퀘스트 점수: {session_score}점" |
| 콤보 보너스 | combo_bonus > 0 → "+{combo_bonus}점 콤보 보너스" |
| 누적 총점 | "전체 누적: {cumulative_score}점" |
| 현재 등급 | "{current_grade} 등급" (뱃지) |
| 등급 상승 메시지 | grade_up_event=true → "축하해요! 이제 {new_grade} 단계예요!" |
| 재시작 버튼 | "새 세션 시작" |

---

## 3. API 명세

### 3.1. 세션 시작

**`POST /api/session/start`**

**Request**
```json
{ "user_id": "string" }
```

**Response**
```json
{
  "session_id": "string",
  "quests": [
    {
      "quest_id": "string",
      "quest_type": "multiple_choice",
      "difficulty": "intro",
      "topic_context": "string",
      "options": ["string", "string", "string", "string"]
    },
    {
      "quest_id": "string",
      "quest_type": "situation_card",
      "difficulty": "main",
      "topic_context": "string",
      "situation": "string"
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
      "quest_type": "situation_card",
      "difficulty": "main_advanced",
      "topic_context": "string",
      "situation": "string"
    },
    {
      "quest_id": "string",
      "quest_type": "battle",
      "difficulty": "main_advanced",
      "topic_context": "string"
    }
  ],
  "user_progress": {
    "cumulative_score": 0,
    "current_grade": "bronze",
    "completed_session_count": 0
  }
}
```

> **주의**: 정답(correct_option_index, explanation, ai_question)은 응답에 포함하지 않는다. 서버에서만 보관.

---

### 3.2. 퀘스트 답변 제출 (Q1~Q4)

**`POST /api/quest/submit`**

**Request (객관식)**
```json
{
  "session_id": "string",
  "quest_id": "string",
  "user_response": 1
}
```

**Request (작성형)**
```json
{
  "session_id": "string",
  "quest_id": "string",
  "user_response": "국어 숙제인데 '내 마음은 호수요'가 왜 비유인지 예시와 함께 설명해줘"
}
```

**Response (객관식)**
```json
{
  "evaluation": {
    "evaluation_type": "correctness",
    "is_correct": true,
    "feedback": "정답이에요! 무엇을, 왜, 어떻게가 모두 들어있어요."
  },
  "earned_score": 20,
  "correct_option_index": 1,
  "combo_count": 0,
  "is_session_complete": false
}
```

**Response (작성형)**
```json
{
  "evaluation": {
    "evaluation_type": "rubric",
    "rubric_result": {
      "specificity": "excellent",
      "context": "excellent",
      "purpose": "excellent",
      "overall": "excellent",
      "rubric_score": 6
    },
    "feedback": "아주 명확해졌어요! 무엇을, 왜, 어떻게 모두 잘 담겨 있어요."
  },
  "earned_score": 30,
  "combo_count": 2,
  "is_session_complete": false
}
```

---

### 3.3. 배틀 라운드 제출 (Q5)

**`POST /api/battle/submit`**

**Request**
```json
{
  "session_id": "string",
  "quest_id": "string",
  "round_number": 1,
  "user_question": "수학 시험 내일인데 이차방정식 인수분해 푸는 법 단계별로 알려줘"
}
```

**Response**
```json
{
  "round_result": {
    "round_number": 1,
    "user_question": "수학 시험 내일인데 이차방정식 인수분해 푸는 법 단계별로 알려줘",
    "ai_question": "이차방정식을 풀 때 인수분해 방법과 근의 공식 중 어떤 방법이 더 빠른지 비교해줘",
    "user_rubric": { "specificity": "excellent", "context": "excellent", "purpose": "excellent", "overall": "excellent", "rubric_score": 6 },
    "ai_rubric": { "specificity": "excellent", "context": "good", "purpose": "excellent", "overall": "good", "rubric_score": 5 },
    "round_winner": "user",
    "earned_score": 20
  },
  "battle_state": {
    "current_round": 1,
    "user_wins": 1,
    "ai_wins": 0,
    "battle_status": "in_progress",
    "is_perfect": false
  },
  "combo_count": 3,
  "next_round_situation": "string (라운드 2 상황카드, 배틀 미완료 시)"
}
```

---

### 3.4. 세션 결과 조회

**`GET /api/session/result?session_id={session_id}`**

**Response**
```json
{
  "session_id": "string",
  "session_score": 110,
  "combo_bonus": 15,
  "battle_bonus": 35,
  "user_progress": {
    "cumulative_score": 260,
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
{ "error_code": "string", "error_message": "string" }
```

| HTTP Status | 에러 코드 | 발생 조건 |
| --- | --- | --- |
| 400 | `E_NO_SELECTION` | 객관식 미선택 제출 |
| 400 | `E_EMPTY_INPUT` | 빈 텍스트 제출 |
| 400 | `E_TOO_SHORT` | 10자 미만 제출 |
| 500 | `E_LLM_TIMEOUT` | LLM 평가 10초 초과 |
| 500 | `E_LLM_INVALID_RESPONSE` | LLM 응답 형식 오류 |
| 500 | `E_QUEST_LOAD_FAIL` | 퀘스트 풀 로드 실패 |

---

## 5. mode별 렌더링 규칙

| mode 값 | 프론트 처리 | 주요 표시 요소 |
| --- | --- | --- |
| `quest_active` (multiple_choice) | S1 화면 표시 | 선택지 4개, 제출 버튼 |
| `quest_active` (situation_card / question_improvement) | S3 화면 표시 | 상황카드 또는 원본 질문, 입력창 |
| `quest_feedback` (correctness) | S2 화면 표시 | 정답 여부, 해설, 점수 |
| `quest_feedback` (rubric) | S4 화면 표시 | 루브릭 뱃지 3종, 피드백, 점수, 콤보 |
| `battle_round_active` | S5 화면 표시 | 상황카드, 입력창, 승리 현황 |
| `battle_round_feedback` | S6 화면 표시 | 비교 표, 라운드 결과, 점수 |
| `battle_completed` | S7 화면 표시 | 최종 결과, 배틀 보너스 |
| `session_completed` | S8 화면 표시 | 총점, 콤보 보너스, 등급, 등급 상승 |
| 에러 | 현재 화면 유지 | 에러 메시지, 재시도 버튼 |

---

## 6. 모듈 간 연결 구조

```
[사용자]
    ↓ 세션 시작
[프론트엔드] → POST /api/session/start
    ↓
[백엔드] → 퀘스트 풀에서 5개 선택
    ↓
[프론트엔드] → quest_sequence 기반으로 화면 순서 관리

[Q1~Q4 흐름]
[프론트엔드] → POST /api/quest/submit (user_response)
    ↓
[백엔드] → LLM 평가 (작성형만) → evaluation 생성
    ↓
[프론트엔드] → mode별 결과 화면 렌더링

[Q5 배틀 흐름]
[프론트엔드] → POST /api/battle/submit (round별 user_question)
    ↓
[백엔드] → LLM 비교 평가 (user vs ai) → round_result 생성
    ↓
[프론트엔드] → 라운드 결과 표시 → 배틀 완료 시 S7

[세션 완료]
[프론트엔드] → GET /api/session/result
    ↓
[백엔드] → 누적 점수·등급 갱신 → grade_up_event 판단
    ↓
[프론트엔드] → S8 세션 완료 화면 렌더링
```
