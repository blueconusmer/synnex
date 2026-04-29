# State Machine — 질문력 강화 퀘스트 서비스

> **문서 성격**: 2차 산출물 (구현 명세서). 서비스의 각 상태와 상태 간 전이 조건, 예외 처리를 정의한 비즈니스 로직 문서.
> **작성 주체**: PM Agent
> **참조 문서**: constitution.md (특히 ④⑦), data_schema.json
> **버전**: v2.0

---

## 1. 상태 목록

| 상태명 | 의미 | 대응 mode 값 |
| --- | --- | --- |
| `session_start` | 세션 초기화, 퀘스트 5개 배치 | — |
| `quest_active` | 현재 퀘스트 진행 중 (Q1~Q4) | `quest_active` |
| `quest_feedback` | 퀘스트 결과·피드백 표시 (Q1~Q4) | `quest_feedback` |
| `battle_round_active` | 배틀 라운드 진행 중 (Q5) | `battle_round_active` |
| `battle_round_feedback` | 배틀 라운드 결과 표시 (Q5) | `battle_round_feedback` |
| `battle_completed` | 배틀 최종 결과 (Q5 완료) | `battle_completed` |
| `session_completed` | 세션 전체 완료, 총점·등급 표시 | `session_completed` |
| `error` | 오류 발생 | — |

---

## 2. data_schema mode 값 매핑

| mode 값 | 반환 필드 |
| --- | --- |
| `quest_active` | quest_id, quest_type, topic_context, situation, original_question, options (객관식만) |
| `quest_feedback` | evaluation, earned_score, combo_count |
| `battle_round_active` | round_number, situation, ai_question (숨김), quest_id |
| `battle_round_feedback` | round_result (user_rubric, ai_rubric, round_winner, earned_score) |
| `battle_completed` | battle_state (user_wins, ai_wins, is_perfect), battle_bonus |
| `session_completed` | session_score, combo_bonus, cumulative_score, current_grade, grade_up_event |
| — (내부 이동) | 반환 없음 |

---

## 3. 상태 전이 규칙

### 3.1. 세션 시작

```
IF 사용자가 "세션 시작" 클릭
   → THEN 상태: session_start (내부)
   → 처리:
       pool에서 각 유형 1개씩 랜덤 선택 (이미 푼 퀘스트 우선 제외)
       quest_sequence = [mc_id, sc_id, qi_id, sc_adv_id, battle_id]
       current_quest_index = 0
       session_score = 0 / combo_count = 0 / combo_bonus = 0
   → THEN 상태: quest_active (Q1 로드)
   → 출력:
       mode: "quest_active"
       quest_type: "multiple_choice"
       [Q1 퀘스트 데이터]
```

### 3.2. Q1 객관식 처리

```
IF 사용자가 선택지 제출 (current_quest_index = 0)
   → THEN 상태: evaluating (내부)

   IF user_response == correct_option_index
      → earned_score = 20
      → is_correct = true
      → feedback = "정답이에요! " + explanation
   ELSE
      → earned_score = 5
      → is_correct = false
      → feedback = "이 선택도 좋지만 더 나은 답이 있어요. " + explanation

   session_score += earned_score
   (Q1은 콤보에 영향 없음)

   → THEN 상태: quest_feedback
   → 출력:
       mode: "quest_feedback"
       evaluation: { evaluation_type: "correctness", is_correct, feedback }
       earned_score
       combo_count (변화 없음)
```

### 3.3. Q2·Q3·Q4 작성형 처리 (병렬 평가)

```
IF 사용자가 작성한 질문 제출 (current_quest_index = 1, 2, 3)
   → THEN 상태: evaluating (내부)
   → LLM_evaluate(user_response) → rubric_result (병렬 평가)

   IF rubric_result.overall == "excellent"
      → earned_score = 30
      → feedback = "아주 명확해졌어요! " + 강점 한 문장
   ELSE IF rubric_result.overall == "needs_work"
      → earned_score = 10
      → feedback = "한 부분이 더 명확해지면 좋겠어요. " + 부족한 영역 한 문장
      → combo_count = 0 (콤보 초기화)
   ELSE (overall == "good")
      → earned_score = 20
      → feedback = "좋아졌어요! " + 개선된 영역 한 문장

   IF rubric_result.overall != "needs_work"
      → combo_count += 1

   session_score += earned_score
   combo_bonus = calculate_combo_bonus(combo_count)

   → THEN 상태: quest_feedback
   → 출력:
       mode: "quest_feedback"
       evaluation: { evaluation_type: "rubric", rubric_result, feedback }
       earned_score
       combo_count
```

### 3.4. Q1~Q4 피드백 → 다음 퀘스트 이동

```
IF 사용자가 "다음" 클릭 (quest_feedback 상태, current_quest_index < 4)
   → current_quest_index += 1

   IF current_quest_index == 4
      → THEN 상태: battle_round_active (라운드 1 시작)
      → battle_state 초기화: { current_round: 1, user_wins: 0, ai_wins: 0, round_results: [], battle_status: "in_progress" }
      → 출력:
          mode: "battle_round_active"
          round_number: 1
          situation: [배틀 퀘스트의 상황 카드]
   ELSE
      → THEN 상태: quest_active (다음 퀘스트 로드)
      → 출력:
          mode: "quest_active"
          [current_quest_index에 해당하는 퀘스트 데이터]
```

### 3.5. Q5 배틀 라운드 처리

```
IF 사용자가 라운드 질문 제출 (battle_round_active 상태)
   → THEN 상태: evaluating (내부)
   → LLM_battle_evaluate(user_question, ai_question) → user_rubric, ai_rubric

   user_score = rubric_score(user_rubric)  // excellent=2, good=1, needs_work=0, 합산 0~6
   ai_score = rubric_score(ai_rubric)

   IF user_score > ai_score
      → round_winner = "user"
      → earned_score = 20
      → battle_state.user_wins += 1
      → combo_count += 1
   ELSE (user_score <= ai_score)
      → round_winner = "ai"
      → earned_score = 5
      → battle_state.ai_wins += 1
      → combo_count = 0

   session_score += earned_score
   combo_bonus = calculate_combo_bonus(combo_count)
   round_results.append(RoundResult)

   → THEN 상태: battle_round_feedback
   → 출력:
       mode: "battle_round_feedback"
       round_result: { round_number, user_question, ai_question, user_rubric, ai_rubric, round_winner, earned_score }
```

### 3.6. 배틀 라운드 피드백 → 다음 라운드 또는 배틀 완료

```
IF 사용자가 "다음 라운드" 클릭 (battle_round_feedback 상태)

   IF user_wins >= 2 OR ai_wins >= 2 OR current_round >= 3
      → THEN 상태: battle_completed

      IF user_wins >= 2
         → battle_status = "user_won"
         → battle_bonus = 20
         IF user_wins == 3 AND current_round == 3
            → is_perfect = true
            → battle_bonus += 15
      ELSE
         → battle_status = "ai_won"
         → battle_bonus = 0

      session_score += battle_bonus
      → 출력:
          mode: "battle_completed"
          battle_state
          battle_bonus

   ELSE
      → current_round += 1
      → THEN 상태: battle_round_active
      → 출력:
          mode: "battle_round_active"
          round_number: current_round
          situation: [다음 라운드 상황 카드]
```

### 3.7. 배틀 완료 → 세션 완료

```
IF 사용자가 "결과 보기" 클릭 (battle_completed 상태)
   → THEN 상태: session_completed (내부)

   previous_grade = user_progress.current_grade
   user_progress.cumulative_score += (session_score + combo_bonus)
   new_grade = determine_grade(user_progress.cumulative_score)
   user_progress.current_grade = new_grade
   user_progress.completed_session_count += 1
   user_progress.completed_quest_ids += session의 quest_sequence

   grade_up_event = (new_grade != previous_grade)

   → 출력:
       mode: "session_completed"
       session_score
       combo_bonus
       cumulative_score: user_progress.cumulative_score
       current_grade: new_grade
       grade_up_event

determine_grade(score):
   IF score >= 600 → "platinum"
   ELSE IF score >= 300 → "gold"
   ELSE IF score >= 100 → "silver"
   ELSE → "bronze"

calculate_combo_bonus(combo_count):
   IF combo_count >= 3 → 15
   ELSE IF combo_count >= 2 → 10
   ELSE → 0
```

---

## 4. 예외 처리 및 에러 메시지

| 예외 조건 | 상태 | 출력 |
| --- | --- | --- |
| 객관식 선택지 미선택 후 제출 | quest_active 유지 | message: "선택지를 골라주세요" |
| 작성형 빈 텍스트 제출 | quest_active 유지 | message: "질문을 작성해주세요" |
| 작성형 10자 미만 제출 | quest_active 유지 | message: "조금 더 자세히 작성해주세요 (최소 10자)" |
| LLM 평가 호출 타임아웃 (10초 초과) | quest_active 유지 | message: "잠시 후 다시 시도해주세요" |
| LLM 평가 응답 형식 오류 | quest_active 유지 | message: "평가 중 문제가 생겼어요. 다시 시도해주세요" |
| 퀘스트 풀 로드 실패 | error | message: "퀘스트를 불러오지 못했어요" |

---

## 5. 포함하지 않는 내용

- 실제 DB 상태 관리 로직 및 서버 내부 처리 방식.
- 구현 방법(코드 레벨). 구현 방식은 Build Plan 참조.
- 재시도 기능 (후속 확장).
- 대화형 힌트 (후속 확장).
