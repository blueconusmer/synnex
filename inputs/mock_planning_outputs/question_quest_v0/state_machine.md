# State Machine — 질문력 강화 퀘스트 서비스 상태 전이표

> **문서 성격**: 2차 산출물 (구현 명세서). User Flow와 QA Plan을 기반으로 작성된 비즈니스 로직 정의.
> **참조 문서**: constitution.md (특히 ⑦ 루브릭 기반 서비스 플로우), data_schema.json
> **버전**: v0.1 (Layer 2 구축용 mock 데이터)

---

## 1. 상태 전이 개요

본 서비스의 한 세션은 다음 7개 상태로 구성된다.

```
[SESSION_START]
    ↓
[QUEST_1_ACTIVE]  (intro 객관식)
    ↓ (제출)
[QUEST_1_FEEDBACK]
    ↓ (확인)
[QUEST_2_ACTIVE]  (main 질문 개선형)
    ↓ (제출)
[QUEST_2_FEEDBACK]
    ↓ (확인)
[QUEST_3_ACTIVE]  (main 질문 개선형)
    ↓ (제출)
[QUEST_3_FEEDBACK]
    ↓ (확인)
[SESSION_COMPLETED]
```

---

## 2. 상태별 정의

| 상태 ID | 사용자 화면 | 주요 동작 | 다음 상태 진입 조건 |
| --- | --- | --- | --- |
| `SESSION_START` | 시작 화면 | 세션 생성, 3개 퀘스트 배치 (intro 1 + main 2) | 사용자가 "시작" 버튼 클릭 |
| `QUEST_1_ACTIVE` | 객관식 퀘스트 화면 | 모호한 원본 질문 + 4개 선택지 표시 | 사용자가 선택지 1개 선택 후 "제출" 클릭 |
| `QUEST_1_FEEDBACK` | 객관식 결과 화면 | 정답/오답 안내 + 해설 + 획득 점수 표시 | 사용자가 "다음" 클릭 |
| `QUEST_2_ACTIVE` | 개선형 퀘스트 화면 | 모호한 원본 질문 + 입력창 표시 | 사용자가 답변 작성 후 "제출" 클릭 |
| `QUEST_2_FEEDBACK` | 개선형 결과 화면 | 루브릭 판정 + 피드백 + 획득 점수 표시 | 사용자가 "다음" 클릭 |
| `QUEST_3_ACTIVE` | 개선형 퀘스트 화면 | (QUEST_2_ACTIVE와 동일 구조) | 사용자가 답변 작성 후 "제출" 클릭 |
| `QUEST_3_FEEDBACK` | 개선형 결과 화면 | (QUEST_2_FEEDBACK과 동일 구조) | 사용자가 "다음" 클릭 |
| `SESSION_COMPLETED` | 세션 결과 화면 | 세션 점수 / 누적 총점 / 현재 등급 표시. 등급 상승 시 축하 메시지 표시 | 사용자가 "새 세션 시작" 또는 "종료" 클릭 |

---

## 3. 상태별 If-Then-Else 로직

### 3.1. `QUEST_1_FEEDBACK` (객관식 결과 처리)

```
입력: user_response (선택한 인덱스), quest.correct_option_index
처리:
  IF user_response == quest.correct_option_index THEN
    evaluation.is_correct = true
    earned_score = 20
    feedback = "정답입니다! " + quest.explanation
  ELSE
    evaluation.is_correct = false
    earned_score = 5
    feedback = "이 질문도 좋지만 더 명확한 선택지가 있어요. " + quest.explanation
  END IF
  session.session_score += earned_score
출력: Evaluation 객체, earned_score
```

### 3.2. `QUEST_2_FEEDBACK` / `QUEST_3_FEEDBACK` (개선형 결과 처리)

```
입력: user_response (작성한 질문 텍스트), quest.original_question
처리:
  rubric_result = LLM_evaluate(user_response, quest.original_question)
  // rubric_result는 specificity, context, purpose 각각 excellent/good/needs_work 판정

  IF rubric_result.specificity == excellent
     AND rubric_result.context == excellent
     AND rubric_result.purpose == excellent THEN
    rubric_result.overall = "excellent"
    earned_score = 30
    feedback = "질문이 아주 명확해졌어요! " + 강점 한 문장
  ELSE IF rubric_result.specificity == needs_work
          OR rubric_result.context == needs_work
          OR rubric_result.purpose == needs_work THEN
    rubric_result.overall = "needs_work"
    earned_score = 10
    feedback = "한 부분이 더 명확해지면 좋겠어요. " + 부족한 영역 한 문장
  ELSE
    rubric_result.overall = "good"
    earned_score = 20
    feedback = "좋아졌어요! " + 개선된 영역 한 문장
  END IF

  session.session_score += earned_score
출력: Evaluation 객체, earned_score
```

### 3.3. `SESSION_COMPLETED` 진입 시 누적 점수·등급 갱신

```
입력: session.session_score, user_progress.cumulative_score (이전), user_progress.current_grade (이전)
처리:
  previous_grade = user_progress.current_grade
  user_progress.cumulative_score += session.session_score
  user_progress.completed_session_count += 1
  new_grade = determine_grade(user_progress.cumulative_score)
  user_progress.current_grade = new_grade

  IF new_grade != previous_grade THEN
    grade_up_event = true
    display_message = "축하해요! 이제 " + new_grade + " 단계예요"
  ELSE
    grade_up_event = false
  END IF
출력: 갱신된 user_progress, grade_up_event 여부

determine_grade(score):
  IF score >= 600 RETURN "platinum"
  ELSE IF score >= 300 RETURN "gold"
  ELSE IF score >= 100 RETURN "silver"
  ELSE RETURN "bronze"
```

---

## 4. 예외 처리 (Edge Case)

| 상황 | 처리 방식 |
| --- | --- |
| 사용자가 객관식에서 선택지를 고르지 않고 제출 | "선택지를 골라주세요" 안내, 상태 유지 |
| 사용자가 개선형에서 빈 텍스트 제출 | "질문을 작성해주세요" 안내, 상태 유지 |
| 사용자가 개선형에서 1자~5자 등 너무 짧은 텍스트 제출 | "조금 더 자세히 작성해주세요 (최소 10자)" 안내, 상태 유지 |
| LLM 평가 호출 실패 (네트워크 오류, 타임아웃) | "잠시 후 다시 시도해주세요" 안내, FEEDBACK 상태 진입 차단 |
| LLM 평가 결과가 정의되지 않은 값 반환 | overall = "good"으로 fallback, 로그 기록 |
| 세션 도중 사용자가 페이지를 닫음 | MVP에서는 세션 상태를 메모리에만 보관하므로 복구 불가. "이어하기" 기능은 후속 확장 |
| 누적 점수가 등급 임계점에 정확히 일치 (예: 100점) | 더 높은 등급으로 처리 (silver) |

---

## 5. 에러 메시지 정의

| 에러 코드 | 사용자 메시지 | 발생 상황 |
| --- | --- | --- |
| `E_NO_SELECTION` | "선택지를 골라주세요" | 객관식 선택지 미선택 시 |
| `E_EMPTY_INPUT` | "질문을 작성해주세요" | 개선형 빈 텍스트 제출 시 |
| `E_TOO_SHORT` | "조금 더 자세히 작성해주세요 (최소 10자)" | 개선형 10자 미만 제출 시 |
| `E_LLM_TIMEOUT` | "잠시 후 다시 시도해주세요" | LLM 평가 호출 타임아웃 (10초 초과) |
| `E_LLM_INVALID_RESPONSE` | "평가 중 문제가 발생했어요. 다시 시도해주세요" | LLM이 정의되지 않은 형식으로 응답 시 |
| `E_QUEST_LOAD_FAIL` | "퀘스트를 불러오지 못했어요" | 퀘스트 콘텐츠 생성 실패 시 |

---

## 6. 상태 전이 보장 사항

본 상태 머신은 다음을 보장한다.

1. **세션 완료 기준**: `SESSION_COMPLETED` 상태에 도달하려면 반드시 3개 퀘스트가 모두 제출되어야 한다.
2. **점수 단조 증가**: `user_progress.cumulative_score`는 어떤 상태 전이에서도 감소하지 않는다.
3. **퀘스트 구성**: 한 세션의 3개 퀘스트는 항상 [intro 1, main 2] 구성이다.
4. **상태 진행 방향**: 한 번 진입한 상태에서 이전 상태로 되돌아갈 수 없다 (재시도는 후속 확장).
5. **LLM 평가 신뢰성**: LLM 평가 실패 시 사용자에게 점수가 부여되지 않으며, 재시도 가능하다.
