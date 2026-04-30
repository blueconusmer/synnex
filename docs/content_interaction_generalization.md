# Content & Interaction Generalization

## 목적

Issue #37의 목표는 `Content & Interaction Agent` 출력 구조를 `QuizItem` 중심에서 `InteractionUnit` 중심으로 일반화하는 것이다.

이 변경은 퀴즈형 서비스만 처리하던 구조를 유지하면서도, 챗봇형/코칭형/혼합형 교육 서비스를 같은 파이프라인에서 표현할 수 있게 만들기 위한 것이다.

## 기존 구조의 한계

- 기존 `ContentInteractionOutput`은 `items`, `quiz_types`, `answer_key` 같은 퀴즈형 필드를 중심으로 설계되어 있었다.
- 이 구조는 객관식 또는 질문 개선형 퀘스트에는 잘 맞지만, 자유 입력, 진단, 되묻기, 코칭 피드백 중심 서비스에는 맞지 않는다.
- Prototype Builder도 화면 흐름을 문제 단위로만 이해하기 쉬워, 비퀴즈형 상호작용을 표현하기가 어려웠다.

## 새 canonical 구조

이제 `interaction_units`를 모든 서비스의 primary contract로 둔다.

각 `InteractionUnit`은 다음 정보를 가진다.

- `unit_id`
- `interaction_type`
- `title`
- `learner_action`
- `system_response`
- `input_format`
- `feedback_rule`
- `learning_dimension`
- `next_step`
- `metadata`

Prototype Builder는 이 구조를 읽어 화면 흐름을 만든다.

- 화면 순서는 `interaction_units` 배열 순서
- 상태 전이는 `next_step`
- 입력 방식은 `interaction_type`와 `input_format`
- 추가 제약은 `metadata`

## QuizItem 하위 호환

기존 질문력 퀘스트 경로는 깨지지 않게 유지한다.

- 퀴즈형 서비스에서는 `items`, `quiz_types`, `answer_key`, `explanations`, `learning_points`를 계속 채운다.
- 동시에 `items`에서 `interaction_units`를 deterministic하게 합성한다.
- 따라서 기존 퀴즈 semantic validator와 regeneration 경로는 유지되고, Builder는 같은 출력에서 더 일반적인 상호작용 흐름도 참고할 수 있다.

## interaction_mode

`interaction_mode`는 app 템플릿 선택자가 아니다.

- `quiz`
- `coaching`
- `general`

세 값은 생성/검증 전략을 고르는 hint로만 사용한다.

- `quiz`: 기존 `QuizItem` 생성 + semantic validator 유지, `interaction_units`도 함께 생성
- `coaching`: `interaction_units` 중심, 자유 입력/진단/코칭 피드백 구조
- `general`: quiz/coaching 어느 한쪽으로 단정하기 어려울 때의 안전한 중립 모드

`general`은 실패 상태가 아니다. mode 추론이 불확실해도 `interaction_units`가 구조 validator를 통과하면 정상 진행한다.

## mode 추론 방식과 한계

mode 추론은 deterministic helper로 수행한다.

- 퀴즈/문항/객관식/정답/점수/quest 성격이 우세하면 `quiz`
- 챗봇/질문 입력/되묻기/진단/coaching `/api/chat` 성격이 우세하면 `coaching`
- 신호가 약하거나 충돌하면 `general`

한계:

- 키워드와 spec 요약을 기반으로 한 보수적 추론이라, 복합 서비스는 `general`로 떨어질 수 있다.
- 이는 의도된 안전장치다. Builder는 `interaction_mode`보다 `interaction_units` 자체를 우선 읽는다.

## feedback 과 coaching_feedback 구분

- `feedback`: 정답/해설/결과에 대한 일반 피드백
- `coaching_feedback`: 사용자 자유 입력을 바탕으로 개선 방향을 제안하는 코칭형 피드백

즉, 퀴즈 해설 결과는 기본적으로 `feedback`이고, 자유 입력 개선 제안은 `coaching_feedback`이다.

## Prototype Builder 연동

Prototype Builder는 `interaction_units`를 app.py 생성의 primary contract로 받는다.

프롬프트에는 다음을 명시적으로 포함한다.

- `interaction_mode`
- `interaction_mode_reason`
- `interaction_units`
- `flow_notes`
- `evaluation_rules`

Builder는 여기서:

- 화면 흐름: `interaction_units` 순서와 `next_step`
- 입력 유형: `interaction_type`, `input_format`
- 평가/피드백 규칙: `evaluation_rules`

를 우선 사용한다.

## #31에서 이어서 검증할 범위

Issue #37은 구조 일반화와 Builder 연동까지를 다룬다.

다음 검증은 Issue #31 범위다.

- `inputs/260428_챗봇/` 기준 결과 비교
- `inputs/260429_퀘스트_v2/` 기준 결과 비교
- service별 live output 의미 정합성 검증
- app.py가 non-quiz interaction_units를 얼마나 자연스럽게 화면으로 옮기는지 검증
