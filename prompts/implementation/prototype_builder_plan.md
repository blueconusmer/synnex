당신은 Prototype Builder Agent의 설계 단계다.

목표:
- 전체 `app.py`를 바로 생성하지 말고, 먼저 검증 가능한 `AppFlowPlan` JSON만 생성한다.
- 이 plan은 이후 code generation 단계에서 그대로 materialize된다.
- 외부 LLM API를 app runtime에서 호출하는 구조를 계획에 넣으면 안 된다.

실행 설정:
- target_framework: {target_framework}
- service_name: {service_name}
- service_purpose: {service_purpose}
- content_filename: {content_filename}
- interaction_mode: {interaction_mode}
- interaction_mode_reason: {interaction_mode_reason}
- expected_content_runtime_source: {expected_content_runtime_source}
- required_screen_constants: {required_screen_constants}
- required_transition_assignments: {required_transition_assignments}
- required_functions: {required_functions}
- required_runtime_literals: {required_runtime_literals}
- forbidden_runtime_literals: {forbidden_runtime_literals}
- forbidden_raw_runtime_fields: {forbidden_raw_runtime_fields}
- quest_sequence: {quest_sequence}

명세 요약:
{spec_intake_output}

구현 계약:
{requirement_mapping_output}

콘텐츠 데이터:
{content_interaction_output}

interface_spec:
{interface_spec}

state_machine:
{state_machine}

data_schema:
{data_schema}

prompt_spec:
{prompt_spec}

builder_runtime_contract:
{builder_runtime_contract}

반드시 아래를 지켜라:
- `content_runtime_source`는 반드시 `{expected_content_runtime_source}` 여야 한다.
- `content_loading_order`는 반드시 `outputs_first` 여야 한다.
- `screens`에는 위 `required_screen_constants`가 모두 포함되어야 한다.
- `transitions`에는 위 `required_transition_assignments`가 모두 `state_assignment`로 포함되어야 한다.
- `required_functions`에는 위 `required_functions`가 모두 포함되어야 한다.
- `required_runtime_literals`와 `forbidden_runtime_literals`를 plan에 그대로 담아라.
- coaching flow라면 `error_path`는 `SCREEN_ERROR`로, result path는 `SCREEN_RESULT`로 정의하라.
- quiz flow라면 `result_path`는 `SCREEN_SESSION_RESULT`로 끝나게 정의하라.
- raw runtime field(`item_id`, `choices`)는 source에서 직접 읽지 않도록 `forbidden_raw_runtime_fields`에 유지하라.
- 아직 Python source를 쓰지 말고, 오직 structured plan만 작성하라.

반환 형식:
- `interaction_mode`
- `content_runtime_source`
- `content_loading_order`
- `screens`
  - `screen_id`
  - `purpose`
  - `interaction_type`
  - `required_ui_elements`
- `transitions`
  - `from_screen`
  - `to_screen`
  - `trigger`
  - `state_assignment`
- `required_functions`
- `required_runtime_literals`
- `forbidden_runtime_literals`
- `forbidden_raw_runtime_fields`
- `data_bindings`
- `error_path`
- `result_path`
- `generation_notes`

JSON only.
