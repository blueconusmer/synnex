"""Prototype builder agent for generating MVP application files."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from clients.llm import LLMClient
from loaders import load_planning_package
from orchestrator.app_source import build_content_filename, build_streamlit_app_source
from schemas.implementation.common import GeneratedFile
from schemas.implementation.prototype_builder import (
    AppSourceGenerationOutput,
    PrototypeBuilderInput,
    PrototypeBuilderOutput,
)

from agents.implementation.helpers import load_prompt_text, make_label


SUPPORTED_TARGET_FRAMEWORKS = {"streamlit"}
KNOWN_UNSUPPORTED_TARGET_FRAMEWORKS = {"react", "fastapi", "nextjs"}
KNOWN_TARGET_FRAMEWORKS = SUPPORTED_TARGET_FRAMEWORKS | KNOWN_UNSUPPORTED_TARGET_FRAMEWORKS
LLM_CALL_FAILED = "LLM_CALL_FAILED"
LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
FALLBACK_USED = "FALLBACK_USED"
CONTRACT_MISSING_MARKER = "CONTRACT_MISSING_MARKER"
RESULT_FLOW_MISSING = "RESULT_FLOW_MISSING"
BATTLE_FLOW_MISSING = "BATTLE_FLOW_MISSING"
COACHING_FLOW_MISSING = "COACHING_FLOW_MISSING"
INTERACTION_UNITS_RUNTIME_MISSING = "INTERACTION_UNITS_RUNTIME_MISSING"
LEGACY_QUEST_RUNTIME_ACCESS = "LEGACY_QUEST_RUNTIME_ACCESS"
ROOT_FIRST_CONTENT_LOADING = "ROOT_FIRST_CONTENT_LOADING"
RAW_FIELD_ACCESS = "RAW_FIELD_ACCESS"
INVALID_STREAMLIT_API = "INVALID_STREAMLIT_API"
PYTHON_SYNTAX_INVALID = "PYTHON_SYNTAX_INVALID"
MISSING_CONTENT_GUIDANCE = "MISSING_CONTENT_GUIDANCE"
PLANNING_PACKAGE_RUNTIME_ACCESS = "PLANNING_PACKAGE_RUNTIME_ACCESS"
MAX_BUILDER_REPAIR_ATTEMPTS = 2
REPAIR_FRIENDLY_CODES = {
    CONTRACT_MISSING_MARKER,
    RESULT_FLOW_MISSING,
    BATTLE_FLOW_MISSING,
    COACHING_FLOW_MISSING,
    INTERACTION_UNITS_RUNTIME_MISSING,
    LEGACY_QUEST_RUNTIME_ACCESS,
    ROOT_FIRST_CONTENT_LOADING,
    RAW_FIELD_ACCESS,
    INVALID_STREAMLIT_API,
    MISSING_CONTENT_GUIDANCE,
}


@dataclass(frozen=True)
class BuilderRuntimeContract:
    """Minimal runtime contract the generated app.py must satisfy."""

    content_filename: str
    interface_screen_ids: list[str]
    required_screen_constants: list[str]
    required_markers: list[str]
    required_transition_assignments: list[str]
    required_functions: list[str]
    required_runtime_literals: list[str]
    forbidden_runtime_literals: list[str]
    forbidden_raw_runtime_fields: list[str]
    normalized_runtime_field_mapping: dict[str, str]
    quest_sequence: list[str]
    requires_battle: bool
    requires_session_result: bool
    interaction_mode: str

    def to_prompt_block(self) -> str:
        return "\n".join(
            [
                "- builder_runtime_contract:",
                f"  - content_filename: {self.content_filename}",
                f"  - interface_screen_ids: {json.dumps(self.interface_screen_ids, ensure_ascii=False)}",
                f"  - required_screen_constants: {json.dumps(self.required_screen_constants, ensure_ascii=False)}",
                f"  - required_markers: {json.dumps(self.required_markers, ensure_ascii=False)}",
                f"  - required_transition_assignments: {json.dumps(self.required_transition_assignments, ensure_ascii=False)}",
                f"  - required_functions: {json.dumps(self.required_functions, ensure_ascii=False)}",
                f"  - required_runtime_literals: {json.dumps(self.required_runtime_literals, ensure_ascii=False)}",
                f"  - forbidden_runtime_literals: {json.dumps(self.forbidden_runtime_literals, ensure_ascii=False)}",
                f"  - forbidden_raw_runtime_fields: {json.dumps(self.forbidden_raw_runtime_fields, ensure_ascii=False)}",
                f"  - normalized_runtime_field_mapping: {json.dumps(self.normalized_runtime_field_mapping, ensure_ascii=False)}",
                f"  - quest_sequence: {json.dumps(self.quest_sequence, ensure_ascii=False)}",
                f"  - requires_battle: {json.dumps(self.requires_battle)}",
                f"  - requires_session_result: {json.dumps(self.requires_session_result)}",
                f"  - interaction_mode: {json.dumps(self.interaction_mode)}",
            ]
        )

    def to_summary_string(self) -> str:
        quest_sequence = " > ".join(self.quest_sequence) if self.quest_sequence else "unknown"
        return (
            f"screens={len(self.required_screen_constants)}, "
            f"battle_required={str(self.requires_battle).lower()}, "
            f"interaction_mode={self.interaction_mode}, "
            f"quest_sequence={quest_sequence}"
        )


class InvalidAppSourceError(ValueError):
    """Raised when the LLM app source does not satisfy minimal runtime constraints."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        contract_items: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.contract_items = contract_items or []


@dataclass(frozen=True)
class ValidatedAppSourceResult:
    app_source: str
    generation_notes: list[str]
    reflection_attempts: int = 0
    repair_attempted: bool = False
    initial_validation_error_code: str = ""
    repair_validation_error_code: str = ""
    repair_history: list[str] = field(default_factory=list)


class BuilderRepairFailed(RuntimeError):
    def __init__(
        self,
        final_error: InvalidAppSourceError,
        *,
        reflection_attempts: int,
        repair_attempted: bool,
        initial_validation_error_code: str,
        repair_validation_error_code: str,
        repair_history: list[str],
    ) -> None:
        super().__init__(final_error.message)
        self.final_error = final_error
        self.reflection_attempts = reflection_attempts
        self.repair_attempted = repair_attempted
        self.initial_validation_error_code = initial_validation_error_code
        self.repair_validation_error_code = repair_validation_error_code
        self.repair_history = repair_history


def run_prototype_builder_agent(
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
) -> PrototypeBuilderOutput:
    """Generate app code artifacts for the current education-service MVP."""

    spec = input_model.implementation_spec
    service_name = spec.service_name or input_model.spec_intake_output.service_summary.split(" ")[0]
    target_framework = _normalize_target_framework(spec.target_framework)
    if target_framework not in SUPPORTED_TARGET_FRAMEWORKS:
        unsupported_reason = _build_unsupported_reason(target_framework)
        return PrototypeBuilderOutput(
            agent=make_label(
                "Prototype Builder Agent",
                "MVP 서비스 코드 생성 Agent",
            ),
            service_name=service_name or "교육 서비스 MVP",
            target_framework=target_framework,
            is_supported=False,
            unsupported_reason=unsupported_reason,
            app_entrypoint="",
            generated_files=[],
            runtime_notes=[unsupported_reason],
            integration_notes=[
                "React/FastAPI/Next.js 생성은 후속 이슈에서 별도 Builder로 확장한다.",
            ],
            generation_mode="unsupported",
            fallback_used=False,
            fallback_reason="",
            generation_inputs_summary=[],
            reflection_attempts=0,
            builder_errors=[],
        )

    content_filename = build_content_filename(service_name)
    package_context = _load_package_prompt_context(Path(spec.source_path))
    builder_runtime_contract = _build_builder_runtime_contract(
        input_model=input_model,
        content_filename=content_filename,
        package_context=package_context,
    )
    generation_inputs_summary = _build_generation_inputs_summary(
        input_model,
        builder_runtime_contract,
    )
    builder_errors: list[str] = []
    fallback_used = False
    fallback_reason = ""
    generation_mode = "llm_generated"
    reflection_attempts = 0
    repair_attempted = False
    initial_validation_error_code = ""
    repair_validation_error_code = ""
    repair_history: list[str] = []

    runtime_notes = [
        f"app.py는 outputs/{content_filename}을 읽는다.",
        "streamlit run app.py로 실행한다.",
    ]
    integration_notes = [
        f"{content_filename}이 outputs/ 아래에 존재해야 한다.",
    ]

    try:
        generation_result = _generate_validated_app_source_with_llm(
            input_model=input_model,
            llm_client=llm_client,
            content_filename=content_filename,
            package_context=package_context,
            builder_runtime_contract=builder_runtime_contract,
        )
        app_source = generation_result.app_source
        runtime_notes.extend(generation_result.generation_notes)
        reflection_attempts = generation_result.reflection_attempts
        repair_attempted = generation_result.repair_attempted
        initial_validation_error_code = generation_result.initial_validation_error_code
        repair_validation_error_code = generation_result.repair_validation_error_code
        repair_history = generation_result.repair_history
        runtime_notes.append(
            f"Builder runtime contract satisfied: {builder_runtime_contract.to_summary_string()}."
        )
        runtime_notes.append("app.py는 LLM 생성 결과를 사용했다.")
    except BuilderRepairFailed as exc:
        builder_errors.extend(
            _dedupe_preserve_order(
                [
                    LLM_OUTPUT_INVALID,
                    exc.initial_validation_error_code,
                    exc.repair_validation_error_code,
                    FALLBACK_USED,
                ]
            )
        )
        fallback_used = True
        fallback_reason = (
            f"{LLM_OUTPUT_INVALID}: {exc.final_error.code}: {exc.final_error.message}"
        )
        generation_mode = "fallback_template"
        app_source = build_fallback_app_source(input_model)
        runtime_notes.append("LLM app.py 출력이 유효하지 않아 fallback template을 사용했다.")
        reflection_attempts = exc.reflection_attempts
        repair_attempted = exc.repair_attempted
        initial_validation_error_code = exc.initial_validation_error_code
        repair_validation_error_code = exc.repair_validation_error_code
        repair_history = exc.repair_history
    except Exception as exc:
        builder_errors.extend([LLM_CALL_FAILED, FALLBACK_USED])
        fallback_used = True
        fallback_reason = f"{LLM_CALL_FAILED}: {exc}"
        generation_mode = "fallback_template"
        app_source = build_fallback_app_source(input_model)
        runtime_notes.append("LLM app.py 생성 호출이 실패해 fallback template을 사용했다.")

    if _is_planning_package_dir(Path(spec.source_path)):
        runtime_notes.append(
            "생성된 app.py는 interface_spec/state_machine에 정의된 Quest 세션 화면 흐름을 반영해야 한다."
        )
        integration_notes.append(
            "score_rules, grade_levels, grade_thresholds는 app.py 생성 시 상수로 삽입된다."
        )
    else:
        runtime_notes.append("planning package 입력이 아니면 Markdown spec 기반 MVP를 생성한다.")
        integration_notes.append("legacy 입력도 서비스별 콘텐츠 파일을 읽어야 한다.")
    if fallback_used:
        integration_notes.append(
            "Fallback template 사용은 LLM-generated app.py 성공으로 간주하지 않는다."
        )
    if repair_history:
        runtime_notes.extend(repair_history)

    return PrototypeBuilderOutput(
        agent=make_label(
            "Prototype Builder Agent",
            "MVP 서비스 코드 생성 Agent",
        ),
        service_name=service_name or "교육 서비스 MVP",
        target_framework=target_framework,
        is_supported=True,
        unsupported_reason="",
        app_entrypoint="app.py",
        generated_files=[
            GeneratedFile(
                path="app.py",
                description="Self-contained Streamlit MVP app generated from service contents.",
                content=app_source,
            )
        ],
        runtime_notes=runtime_notes,
        integration_notes=integration_notes,
        generation_mode=generation_mode,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        generation_inputs_summary=generation_inputs_summary,
        reflection_attempts=reflection_attempts,
        repair_attempted=repair_attempted,
        initial_validation_error_code=initial_validation_error_code,
        repair_validation_error_code=repair_validation_error_code,
        repair_history=repair_history,
        builder_errors=builder_errors,
    )


def build_fallback_app_source(input_model: PrototypeBuilderInput) -> str:
    """Build the deterministic Streamlit fallback app source.

    This is intentionally not used on the normal supported path unless LLM generation
    or reflection cannot produce a runnable app.py.
    """

    spec = input_model.implementation_spec
    service_name = spec.service_name or "교육 서비스 MVP"
    content_filename = build_content_filename(service_name)
    source_path = Path(spec.source_path)

    if _is_planning_package_dir(source_path):
        package = load_planning_package(source_path)
        score_rules = dict(package.evaluation_spec.score_rules)
        grade_levels = list(package.evaluation_spec.grade_levels)
        grade_thresholds = _normalize_grade_thresholds(
            score_rules.get("service_grades", {}),
            grade_levels,
        )
        return build_streamlit_app_source(
            service_name=service_name,
            content_filename=content_filename,
            interaction_mode=input_model.content_interaction_output.interaction_mode,
            screens=list(package.interface_spec.screens),
            api_endpoints=list(package.interface_spec.api_endpoints),
            score_rules=score_rules,
            grade_levels=grade_levels,
            grade_thresholds=grade_thresholds,
        )

    return build_streamlit_app_source(
        service_name=service_name,
        content_filename=content_filename,
        interaction_mode=input_model.content_interaction_output.interaction_mode,
    )


def _generate_app_source_with_llm(
    *,
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
    content_filename: str,
    package_context: dict[str, str],
    builder_runtime_contract: BuilderRuntimeContract,
) -> AppSourceGenerationOutput:
    prompt = _build_app_generation_prompt(
        input_model=input_model,
        content_filename=content_filename,
        package_context=package_context,
        builder_runtime_contract=builder_runtime_contract,
    )
    return llm_client.generate_json(
        prompt=prompt,
        response_model=AppSourceGenerationOutput,
        system_prompt=(
            "You are a senior Python engineer generating one runnable Streamlit app.py. "
            "Return JSON only. The app must be self-contained and must not call external LLM APIs."
        ),
    )


def _generate_validated_app_source_with_llm(
    *,
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
    content_filename: str,
    package_context: dict[str, str],
    builder_runtime_contract: BuilderRuntimeContract,
) -> ValidatedAppSourceResult:
    generated_app = _generate_app_source_with_llm(
        input_model=input_model,
        llm_client=llm_client,
        content_filename=content_filename,
        package_context=package_context,
        builder_runtime_contract=builder_runtime_contract,
    )
    try:
        validated_source = _validate_generated_app_source(
            generated_app=generated_app,
            content_filename=content_filename,
            builder_runtime_contract=builder_runtime_contract,
        )
        return ValidatedAppSourceResult(
            app_source=validated_source,
            generation_notes=_dedupe_preserve_order(
                [
                    *generated_app.generation_notes,
                    _build_contract_self_check_note(validated_source, builder_runtime_contract),
                ]
            ),
        )
    except InvalidAppSourceError as first_error:
        return _repair_invalid_app_source_with_llm(
            input_model=input_model,
            llm_client=llm_client,
            content_filename=content_filename,
            invalid_source=generated_app.app_source,
            first_error=first_error,
            generated_app=generated_app,
            builder_runtime_contract=builder_runtime_contract,
        )


def _repair_invalid_app_source_with_llm(
    *,
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
    content_filename: str,
    invalid_source: str,
    first_error: InvalidAppSourceError,
    generated_app: AppSourceGenerationOutput,
    builder_runtime_contract: BuilderRuntimeContract,
) -> ValidatedAppSourceResult:
    repair_history = [
        _format_repair_history_entry(
            attempt_number=0,
            error=first_error,
            status="FAILED",
            note="Initial generation failed validation.",
        )
    ]
    if not _is_repair_friendly_error(first_error):
        raise BuilderRepairFailed(
            first_error,
            reflection_attempts=0,
            repair_attempted=False,
            initial_validation_error_code=first_error.code,
            repair_validation_error_code="",
            repair_history=repair_history + ["Repair skipped: failure was not repair-friendly."],
        )

    previous_error = first_error
    current_invalid_source = invalid_source
    repair_attempts = 0
    generation_notes = list(generated_app.generation_notes)

    for attempt_number in range(1, MAX_BUILDER_REPAIR_ATTEMPTS + 1):
        repair_attempts = attempt_number
        repair_prompt = _build_app_validation_repair_prompt(
            input_model=input_model,
            content_filename=content_filename,
            invalid_source=current_invalid_source,
            validation_error=previous_error,
            builder_runtime_contract=builder_runtime_contract,
            repair_attempt_number=attempt_number,
            max_repair_attempts=MAX_BUILDER_REPAIR_ATTEMPTS,
            repair_history=repair_history,
        )
        try:
            repaired_app = llm_client.generate_json(
                prompt=repair_prompt,
                response_model=AppSourceGenerationOutput,
                system_prompt=(
                    "You fix one generated Streamlit app.py so it satisfies the runtime contract. "
                    "Return JSON only. Do not call external LLM APIs."
                ),
            )
        except Exception as exc:
            repair_history.append(
                f"Repair attempt {attempt_number} failed before validation: LLM_CALL_FAILED ({exc})."
            )
            raise BuilderRepairFailed(
                InvalidAppSourceError(LLM_CALL_FAILED, f"Repair attempt {attempt_number} LLM call failed: {exc}."),
                reflection_attempts=repair_attempts,
                repair_attempted=True,
                initial_validation_error_code=first_error.code,
                repair_validation_error_code=LLM_CALL_FAILED,
                repair_history=repair_history,
            ) from exc

        try:
            repaired_source = _validate_generated_app_source(
                generated_app=repaired_app,
                content_filename=content_filename,
                builder_runtime_contract=builder_runtime_contract,
            )
            repair_history.append(
                f"Repair attempt {attempt_number} succeeded after {previous_error.code}."
            )
            return ValidatedAppSourceResult(
                app_source=repaired_source,
                generation_notes=_dedupe_preserve_order(
                    [
                        *generation_notes,
                        f"Initial app_source failed validation once with {first_error.code}.",
                        *repaired_app.generation_notes,
                        _build_contract_self_check_note(repaired_source, builder_runtime_contract),
                    ]
                ),
                reflection_attempts=repair_attempts,
                repair_attempted=True,
                initial_validation_error_code=first_error.code,
                repair_validation_error_code="",
                repair_history=repair_history,
            )
        except InvalidAppSourceError as repair_error:
            repair_history.append(
                _format_repair_history_entry(
                    attempt_number=attempt_number,
                    error=repair_error,
                    status="FAILED",
                    note=f"Repair attempt {attempt_number} failed validation.",
                )
            )
            stop_reason = _repair_stop_reason(previous_error, repair_error)
            if stop_reason:
                repair_history.append(
                    f"Repair stopped after attempt {attempt_number}: {stop_reason}"
                )
                raise BuilderRepairFailed(
                    repair_error,
                    reflection_attempts=repair_attempts,
                    repair_attempted=True,
                    initial_validation_error_code=first_error.code,
                    repair_validation_error_code=repair_error.code,
                    repair_history=repair_history,
                )
            if not _is_repair_friendly_error(repair_error):
                repair_history.append(
                    f"Repair stopped after attempt {attempt_number}: failure was not repair-friendly."
                )
                raise BuilderRepairFailed(
                    repair_error,
                    reflection_attempts=repair_attempts,
                    repair_attempted=True,
                    initial_validation_error_code=first_error.code,
                    repair_validation_error_code=repair_error.code,
                    repair_history=repair_history,
                )
            previous_error = repair_error
            current_invalid_source = repaired_app.app_source

    raise BuilderRepairFailed(
        previous_error,
        reflection_attempts=repair_attempts,
        repair_attempted=repair_attempts > 0,
        initial_validation_error_code=first_error.code,
        repair_validation_error_code=previous_error.code,
        repair_history=repair_history
        + [f"Repair budget exhausted after {repair_attempts} attempts."],
    )


def _build_app_generation_prompt(
    *,
    input_model: PrototypeBuilderInput,
    content_filename: str,
    package_context: dict[str, str],
    builder_runtime_contract: BuilderRuntimeContract,
) -> str:
    spec = input_model.implementation_spec
    prompt_template = load_prompt_text("prototype_builder.md")
    context = {
        "target_framework": spec.target_framework,
        "service_name": spec.service_name,
        "service_purpose": spec.service_purpose,
        "target_user": ", ".join(spec.target_users),
        "mvp_scope": spec.core_features,
        "content_filename": content_filename,
        "spec_intake_output": input_model.spec_intake_output.model_dump(mode="json"),
        "requirement_mapping_output": input_model.requirement_mapping_output.model_dump(mode="json"),
        "content_interaction_output": input_model.content_interaction_output.model_dump(mode="json"),
        "interface_spec": package_context.get("interface_spec", ""),
        "state_machine": package_context.get("state_machine", ""),
        "data_schema": package_context.get("data_schema", ""),
        "prompt_spec": package_context.get("prompt_spec", ""),
        "interaction_mode": input_model.content_interaction_output.interaction_mode,
        "interaction_mode_reason": input_model.content_interaction_output.interaction_mode_reason,
        "interaction_units": [
            unit.model_dump(mode="json")
            for unit in input_model.content_interaction_output.interaction_units
        ],
        "flow_notes": input_model.content_interaction_output.flow_notes,
        "evaluation_rules": input_model.content_interaction_output.evaluation_rules,
        "builder_runtime_contract": builder_runtime_contract.to_prompt_block(),
    }
    return prompt_template.format(
        target_framework=context["target_framework"],
        service_name=context["service_name"],
        service_purpose=context["service_purpose"],
        target_user=context["target_user"],
        mvp_scope=json.dumps(context["mvp_scope"], ensure_ascii=False),
        content_filename=context["content_filename"],
        spec_intake_output=json.dumps(context["spec_intake_output"], ensure_ascii=False, indent=2),
        requirement_mapping_output=json.dumps(
            context["requirement_mapping_output"],
            ensure_ascii=False,
            indent=2,
        ),
        content_interaction_output=json.dumps(
            context["content_interaction_output"],
            ensure_ascii=False,
            indent=2,
        ),
        interface_spec=context["interface_spec"],
        state_machine=context["state_machine"],
        data_schema=context["data_schema"],
        prompt_spec=context["prompt_spec"],
        interaction_mode=context["interaction_mode"],
        interaction_mode_reason=context["interaction_mode_reason"],
        interaction_units=json.dumps(context["interaction_units"], ensure_ascii=False, indent=2),
        flow_notes=json.dumps(context["flow_notes"], ensure_ascii=False, indent=2),
        evaluation_rules=json.dumps(
            context["evaluation_rules"],
            ensure_ascii=False,
            indent=2,
        ),
        builder_runtime_contract=context["builder_runtime_contract"],
    )


def _build_app_validation_repair_prompt(
    *,
    input_model: PrototypeBuilderInput,
    content_filename: str,
    invalid_source: str,
    validation_error: InvalidAppSourceError,
    builder_runtime_contract: BuilderRuntimeContract,
    repair_attempt_number: int,
    max_repair_attempts: int,
    repair_history: list[str],
) -> str:
    spec = input_model.implementation_spec
    failed_items = validation_error.contract_items or [validation_error.message]
    return (
        "The previous generated app.py failed validation.\n"
        f"Repair attempt: {repair_attempt_number} / {max_repair_attempts}\n"
        f"Validation error code: {validation_error.code}\n"
        f"Validation error: {validation_error.message}\n\n"
        "Preserve the valid parts of the existing source and add or fix only the missing runtime contract items.\n"
        "Modify the smallest possible set of lines.\n"
        "Do not rewrite unrelated functions.\n"
        "Do not drop valid helper functions, content loading logic, or current_screen transitions.\n"
        "Do not rename screen constants, helper functions, or session state keys.\n"
        "If a missing contract item is shown as a literal assignment or literal marker, insert that exact literal.\n\n"
        "Builder runtime contract:\n"
        f"{builder_runtime_contract.to_prompt_block()}\n\n"
        "Missing or invalid contract items:\n"
        f"{json.dumps(failed_items, ensure_ascii=False, indent=2)}\n\n"
        "Repair history so far:\n"
        f"{json.dumps(repair_history, ensure_ascii=False, indent=2)}\n\n"
        "Required functions to preserve:\n"
        f"{json.dumps(builder_runtime_contract.required_functions, ensure_ascii=False)}\n\n"
        "Targeted repair guidance:\n"
        f"{_build_repair_guidance(validation_error, builder_runtime_contract)}\n\n"
        "The corrected source must satisfy this mandatory content loading contract:\n\n"
        f"{_mandatory_content_loading_contract(content_filename)}\n\n"
        "Do not read planning package files at runtime.\n"
        "Do not call external LLM APIs.\n"
        "Return JSON with app_path='app.py', app_source, and generation_notes.\n\n"
        f"service_name: {spec.service_name}\n"
        f"target_framework: {spec.target_framework}\n"
        f"content_filename: {content_filename}\n\n"
        "Previous invalid app_source:\n"
        f"{invalid_source}"
    )


def _is_repair_friendly_error(error: InvalidAppSourceError) -> bool:
    contract_items = error.contract_items or [error.message]
    return error.code in REPAIR_FRIENDLY_CODES and len(contract_items) <= 2


def _repair_stop_reason(
    previous_error: InvalidAppSourceError,
    current_error: InvalidAppSourceError,
) -> str:
    previous_items = previous_error.contract_items or [previous_error.message]
    current_items = current_error.contract_items or [current_error.message]
    if current_error.code == previous_error.code:
        return f"same validation error code repeated ({current_error.code})"
    if current_items == previous_items:
        return "contract items did not change between repair attempts"
    return ""


def _format_repair_history_entry(
    *,
    attempt_number: int,
    error: InvalidAppSourceError,
    status: str,
    note: str,
) -> str:
    contract_items = ", ".join(error.contract_items or []) or "none"
    label = "initial_validation" if attempt_number == 0 else f"repair_attempt_{attempt_number}"
    return (
        f"{label}: {status} code={error.code}; "
        f"contract_items=[{contract_items}]; note={note}"
    )


def _validate_generated_app_source(
    *,
    generated_app: AppSourceGenerationOutput,
    content_filename: str,
    builder_runtime_contract: BuilderRuntimeContract,
) -> str:
    app_path = Path(generated_app.app_path or "app.py")
    if app_path.name != "app.py":
        raise InvalidAppSourceError(
            CONTRACT_MISSING_MARKER,
            "LLM output app_path must point to app.py.",
            contract_items=["app_path=app.py"],
        )

    app_source = _strip_python_fence(generated_app.app_source)
    if not app_source.strip():
        raise InvalidAppSourceError(CONTRACT_MISSING_MARKER, "LLM output app_source is empty.")
    if "st." not in app_source or "streamlit" not in app_source:
        raise InvalidAppSourceError(
            CONTRACT_MISSING_MARKER,
            "app_source does not appear to be a Streamlit app.",
        )
    if content_filename not in app_source:
        raise InvalidAppSourceError(
            CONTRACT_MISSING_MARKER,
            f"app_source does not reference required content file {content_filename}.",
            contract_items=[content_filename],
        )
    if not _references_outputs_content_path(app_source, content_filename):
        raise InvalidAppSourceError(
            CONTRACT_MISSING_MARKER,
            f"app_source must reference outputs/{content_filename} as a content candidate.",
            contract_items=[f"outputs/{content_filename}"],
        )
    if not _uses_outputs_before_root_fallback(app_source, content_filename):
        raise InvalidAppSourceError(
            ROOT_FIRST_CONTENT_LOADING,
            "app_source must try outputs/{content_filename} before the root fallback file."
        )
    if not _has_missing_content_guidance(app_source):
        raise InvalidAppSourceError(
            MISSING_CONTENT_GUIDANCE,
            "app_source must show user-facing guidance when the content file is missing."
        )
    if "st.experimental_rerun" in app_source:
        raise InvalidAppSourceError(
            INVALID_STREAMLIT_API,
            "app_source must use st.rerun() instead of st.experimental_rerun().",
            contract_items=["st.rerun()"],
        )
    try:
        compile(app_source, "app.py", "exec")
    except SyntaxError as exc:
        raise InvalidAppSourceError(
            PYTHON_SYNTAX_INVALID,
            f"app_source is not valid Python: {exc.msg} at line {exc.lineno}."
        ) from exc
    _validate_state_machine_contract(app_source, builder_runtime_contract)
    _validate_runtime_content_contract(app_source, builder_runtime_contract)
    _validate_function_call_arity(
        app_source=app_source,
        function_name="evaluate_improvement_question",
    )
    forbidden_runtime_inputs = [
        "load_planning_package",
        "constitution.md",
        "data_schema.json",
        "state_machine.md",
        "prompt_spec.md",
        "interface_spec.md",
    ]
    for forbidden in forbidden_runtime_inputs:
        if forbidden in app_source:
            raise InvalidAppSourceError(
                PLANNING_PACKAGE_RUNTIME_ACCESS,
                f"app_source must not read planning package input at runtime: {forbidden}."
            )
    return app_source.rstrip() + "\n"


def _validate_state_machine_contract(
    app_source: str,
    builder_runtime_contract: BuilderRuntimeContract,
) -> None:
    normalized = _normalize_source_for_contract_checks(app_source)
    required_markers = [
        *builder_runtime_contract.required_markers,
        *builder_runtime_contract.required_screen_constants,
    ]
    for marker in required_markers:
        if marker not in app_source:
            raise InvalidAppSourceError(
                _classify_contract_issue(marker),
                f"app_source must include state-machine marker: {marker}.",
                contract_items=[marker],
            )

    for assignment in builder_runtime_contract.required_transition_assignments:
        if _normalize_source_for_contract_checks(assignment) not in normalized:
            raise InvalidAppSourceError(
                _classify_contract_issue(assignment),
                f"app_source must include state transition assignment: {assignment}.",
                contract_items=[assignment],
            )

    runtime_source = _strip_allowed_normalization_blocks(
        app_source,
        allowed_function_names={"normalize_quest"},
    )
    for pattern in builder_runtime_contract.forbidden_raw_runtime_fields:
        if pattern in runtime_source:
            raise InvalidAppSourceError(
                RAW_FIELD_ACCESS,
                "app_source must use normalized quest fields only; "
                f"found raw field reference {pattern} outside normalization helpers.",
                contract_items=[pattern],
            )


def _validate_runtime_content_contract(
    app_source: str,
    builder_runtime_contract: BuilderRuntimeContract,
) -> None:
    normalized = _normalize_source_for_contract_checks(app_source)
    for literal in builder_runtime_contract.required_runtime_literals:
        normalized_literal = _normalize_source_for_contract_checks(literal)
        if normalized_literal not in normalized:
            raise InvalidAppSourceError(
                _classify_contract_issue(literal),
                f"app_source must include runtime contract literal: {literal}.",
                contract_items=[literal],
            )
    for literal in builder_runtime_contract.forbidden_runtime_literals:
        normalized_literal = _normalize_source_for_contract_checks(literal)
        if normalized_literal in normalized:
            raise InvalidAppSourceError(
                LEGACY_QUEST_RUNTIME_ACCESS,
                f"app_source must not use legacy quiz runtime access pattern: {literal}.",
                contract_items=[literal],
            )


def _validate_function_call_arity(*, app_source: str, function_name: str) -> None:
    tree = ast.parse(app_source)
    definitions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    if not definitions:
        return

    definition = definitions[0]
    positional_args = [*definition.args.posonlyargs, *definition.args.args]
    required_count = len(positional_args) - len(definition.args.defaults)
    max_count = None if definition.args.vararg else len(positional_args)
    arg_names = {arg.arg for arg in positional_args}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_call_to_function(node, function_name):
            continue

        positional_count = len(node.args)
        keyword_names = {
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None and keyword.arg in arg_names
        }
        provided_count = positional_count + len(keyword_names)
        if max_count is not None and positional_count > max_count:
            raise InvalidAppSourceError(
                CONTRACT_MISSING_MARKER,
                f"{function_name} call passes {positional_count} positional args "
                f"but function defines {max_count}.",
                contract_items=[function_name],
            )
        if provided_count < required_count:
            raise InvalidAppSourceError(
                CONTRACT_MISSING_MARKER,
                f"{function_name} call provides {provided_count} args "
                f"but function requires {required_count}.",
                contract_items=[function_name],
            )


def _is_call_to_function(node: ast.Call, function_name: str) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == function_name
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == function_name
    return False


def _references_outputs_content_path(app_source: str, content_filename: str) -> bool:
    normalized = _normalize_source_for_contract_checks(app_source)
    exact_outputs_path = f"outputs/{content_filename}".lower()
    return (
        exact_outputs_path in normalized
        or '"outputs"/content_filename' in normalized
        or "'outputs'/content_filename" in normalized
        or '/"outputs"/content_filename' in normalized
        or "/'outputs'/content_filename" in normalized
    )


def _uses_outputs_before_root_fallback(app_source: str, content_filename: str) -> bool:
    compact = _normalize_source_for_contract_checks(app_source)
    outputs_first_patterns = [
        "content_candidate_paths=[output_path,fallback_output_path]",
        "candidate_paths=[output_path,fallback_output_path]",
        "content_paths=[output_path,fallback_output_path]",
        "content_candidate_paths=[outputs_path,root_path]",
        "candidate_paths=[outputs_path,root_path]",
        "content_paths=[outputs_path,root_path]",
        "content_candidate_paths=[output_path,root_path]",
        "candidate_paths=[output_path,root_path]",
        "content_paths=[output_path,root_path]",
    ]
    if any(pattern in compact for pattern in outputs_first_patterns):
        return True

    exact_outputs_path = f"outputs/{content_filename}".lower()
    root_first_patterns = [
        f"content_path='{content_filename.lower()}'",
        f'content_path="{content_filename.lower()}"',
        f"content_path=app_dir/'{content_filename.lower()}'",
        f'content_path=app_dir/"{content_filename.lower()}"',
    ]
    if exact_outputs_path in compact and any(pattern in compact for pattern in root_first_patterns):
        root_first_index = min(
            compact.find(pattern)
            for pattern in root_first_patterns
            if pattern in compact
        )
        output_index = compact.find(exact_outputs_path)
        return output_index < root_first_index

    return exact_outputs_path in compact


def _has_missing_content_guidance(app_source: str) -> bool:
    lowered = app_source.lower()
    guidance_markers = [
        "st.warning",
        "st.error",
        "콘텐츠 파일",
        "content file",
        "not found",
        "찾지 못",
        "없습니다",
    ]
    return any(marker in lowered for marker in guidance_markers)


def _normalize_source_for_contract_checks(app_source: str) -> str:
    return "".join(app_source.lower().split())


def _strip_allowed_normalization_blocks(
    app_source: str,
    *,
    allowed_function_names: set[str],
) -> str:
    tree = ast.parse(app_source)
    source_lines = app_source.splitlines()
    removed_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name not in allowed_function_names:
            continue
        start = node.lineno - 1
        end = getattr(node, "end_lineno", node.lineno) - 1
        removed_ranges.append((start, end))

    kept_lines: list[str] = []
    for index, line in enumerate(source_lines):
        if any(start <= index <= end for start, end in removed_ranges):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def _strip_python_fence(source: str) -> str:
    stripped = source.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return source


def _load_package_prompt_context(path: Path) -> dict[str, str]:
    if not _is_planning_package_dir(path):
        return {}

    file_map = {
        "interface_spec": "interface_spec.md",
        "state_machine": "state_machine.md",
        "data_schema": "data_schema.json",
        "prompt_spec": "prompt_spec.md",
    }
    context: dict[str, str] = {}
    for key, file_name in file_map.items():
        file_path = path / file_name
        context[key] = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    return context


def _build_generation_inputs_summary(
    input_model: PrototypeBuilderInput,
    builder_runtime_contract: BuilderRuntimeContract,
) -> list[str]:
    spec = input_model.implementation_spec
    summary = [
        f"target_framework={spec.target_framework}",
        f"service_purpose={'present' if spec.service_purpose else 'missing'}",
        f"target_user_count={len(spec.target_users)}",
        f"mvp_scope_count={len(spec.core_features)}",
        f"interaction_mode={input_model.content_interaction_output.interaction_mode}",
        f"interaction_unit_count={len(input_model.content_interaction_output.interaction_units)}",
        f"builder_contract_screen_count={len(builder_runtime_contract.required_screen_constants)}",
        f"builder_contract_battle_required={str(builder_runtime_contract.requires_battle).lower()}",
        f"builder_contract_quest_sequence={'>'.join(builder_runtime_contract.quest_sequence)}",
        "spec_intake_output",
        "requirement_mapping_output",
        "content_interaction_output",
        "builder_runtime_contract",
    ]
    if _is_planning_package_dir(Path(spec.source_path)):
        summary.extend(["interface_spec", "state_machine", "data_schema", "prompt_spec"])
    return summary


def _mandatory_content_loading_contract(content_filename: str) -> str:
    return (
        "from pathlib import Path\n\n"
        f'CONTENT_FILENAME = "{content_filename}"\n'
        "APP_DIR = Path(__file__).resolve().parent\n"
        'OUTPUT_PATH = APP_DIR / "outputs" / CONTENT_FILENAME\n'
        "FALLBACK_OUTPUT_PATH = APP_DIR / CONTENT_FILENAME\n"
        "CONTENT_CANDIDATE_PATHS = [OUTPUT_PATH, FALLBACK_OUTPUT_PATH]\n\n"
        "def resolve_content_path() -> Path | None:\n"
        "    for candidate in CONTENT_CANDIDATE_PATHS:\n"
        "        if candidate.exists():\n"
        "            return candidate\n"
        "    return None\n\n"
        "# If resolve_content_path() returns None, show st.warning or st.error with a clear message.\n"
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _build_builder_runtime_contract(
    *,
    input_model: PrototypeBuilderInput,
    content_filename: str,
    package_context: dict[str, str],
) -> BuilderRuntimeContract:
    interaction_mode = input_model.content_interaction_output.interaction_mode
    quest_sequence = [item.quiz_type for item in input_model.content_interaction_output.items]
    if not quest_sequence:
        quest_sequence = [
            (
                unit.metadata.get("source_quiz_type", "")
                if isinstance(unit.metadata, dict)
                else ""
            )
            or unit.interaction_type
            for unit in input_model.content_interaction_output.interaction_units
        ]
        quest_sequence = [value for value in quest_sequence if value]

    uses_interaction_units_runtime = (
        interaction_mode == "coaching"
        and not input_model.content_interaction_output.items
    )
    if uses_interaction_units_runtime:
        return BuilderRuntimeContract(
            content_filename=content_filename,
            interface_screen_ids=_extract_interface_screen_ids(package_context.get("interface_spec", "")),
            required_screen_constants=[
                "SCREEN_START",
                "SCREEN_INPUT",
                "SCREEN_FOLLOW_UP",
                "SCREEN_RESULT",
                "SCREEN_ERROR",
            ],
            required_markers=["current_screen", "st.rerun()"],
            required_transition_assignments=[
                "st.session_state.current_screen = SCREEN_INPUT",
                "st.session_state.current_screen = SCREEN_FOLLOW_UP",
                "st.session_state.current_screen = SCREEN_RESULT",
                "st.session_state.current_screen = SCREEN_ERROR",
            ],
            required_functions=["api_session_start", "api_chat_submit", "api_session_result"],
            required_runtime_literals=['get("interaction_units"', "interaction_units", "def api_chat_submit"],
            forbidden_runtime_literals=['get("quests"', "['quests']", '["quests"]'],
            forbidden_raw_runtime_fields=[],
            normalized_runtime_field_mapping={},
            quest_sequence=quest_sequence,
            requires_battle=False,
            requires_session_result=True,
            interaction_mode=interaction_mode,
        )

    requires_battle = "battle" in quest_sequence or any(
        "battle" in note.lower() for note in input_model.content_interaction_output.flow_notes
    )
    required_screen_constants = [
        "SCREEN_START",
        "SCREEN_MULTIPLE_CHOICE",
        "SCREEN_MULTIPLE_CHOICE_RESULT",
        "SCREEN_IMPROVEMENT",
        "SCREEN_IMPROVEMENT_RESULT",
        "SCREEN_SESSION_RESULT",
    ]
    required_transition_assignments = [
        "st.session_state.current_screen = SCREEN_MULTIPLE_CHOICE_RESULT",
        "st.session_state.current_screen = SCREEN_IMPROVEMENT_RESULT",
        "st.session_state.current_screen = SCREEN_SESSION_RESULT",
    ]
    if requires_battle:
        required_screen_constants.extend(
            [
                "SCREEN_BATTLE",
                "SCREEN_BATTLE_RESULT",
                "SCREEN_BATTLE_COMPLETED",
            ]
        )
        required_transition_assignments.extend(
            [
                "st.session_state.current_screen = SCREEN_BATTLE",
                "st.session_state.current_screen = SCREEN_BATTLE_RESULT",
                "st.session_state.current_screen = SCREEN_BATTLE_COMPLETED",
            ]
        )
    return BuilderRuntimeContract(
        content_filename=content_filename,
        interface_screen_ids=_extract_interface_screen_ids(package_context.get("interface_spec", "")),
        required_screen_constants=required_screen_constants,
        required_markers=["current_screen", "st.rerun()"],
        required_transition_assignments=required_transition_assignments,
        required_functions=["api_session_start", "api_quest_submit", "api_session_result"],
        required_runtime_literals=[],
        forbidden_runtime_literals=[],
        forbidden_raw_runtime_fields=[
            'quest["item_id"]',
            "quest['item_id']",
            'quest.get("item_id"',
            "quest.get('item_id'",
            'quest["choices"]',
            "quest['choices']",
            'quest.get("choices"',
            "quest.get('choices'",
        ],
        normalized_runtime_field_mapping={
            'item["item_id"]': 'quest["quest_id"]',
            'quest["item_id"]': 'quest["quest_id"]',
            'item["choices"]': 'quest["options"]',
            'quest["choices"]': 'quest["options"]',
            'item["correct_choice"]': 'quest["correct_option_text"]',
            'quest["correct_choice"]': 'quest["correct_option_text"]',
        },
        quest_sequence=quest_sequence,
        requires_battle=requires_battle,
        requires_session_result=True,
        interaction_mode=interaction_mode,
    )


def _build_contract_self_check_note(
    app_source: str,
    builder_runtime_contract: BuilderRuntimeContract,
) -> str:
    normalized = _normalize_source_for_contract_checks(app_source)
    required_markers = [
        *builder_runtime_contract.required_markers,
        *builder_runtime_contract.required_screen_constants,
    ]
    marker_count = sum(1 for marker in required_markers if marker in app_source)
    transition_count = sum(
        1
        for assignment in builder_runtime_contract.required_transition_assignments
        if _normalize_source_for_contract_checks(assignment) in normalized
    )
    outputs_first_loading = _uses_outputs_before_root_fallback(
        app_source,
        builder_runtime_contract.content_filename,
    )
    return (
        "Builder self-check: "
        f"markers={marker_count}/{len(required_markers)}, "
        f"transitions={transition_count}/{len(builder_runtime_contract.required_transition_assignments)}, "
        f"battle_required={str(builder_runtime_contract.requires_battle).lower()}, "
        f"outputs_first_loading={str(outputs_first_loading).lower()}"
    )


def _build_repair_guidance(
    validation_error: InvalidAppSourceError,
    builder_runtime_contract: BuilderRuntimeContract,
) -> str:
    guidance = [
        "Keep the existing file structure when possible and only repair the failed runtime contract items.",
        "Keep current_screen-based transitions explicit with literal assignments in source.",
        "Keep outputs/{content_filename} first and root fallback second.".replace(
            "{content_filename}",
            builder_runtime_contract.content_filename,
        ),
    ]
    if validation_error.code == RAW_FIELD_ACCESS:
        guidance.extend(
            [
                "Only normalize_quest(item) may read raw item fields such as item_id or choices.",
                "Replace quest[\"item_id\"] with quest[\"quest_id\"] everywhere outside normalize_quest(item).",
                "Replace quest[\"choices\"] with quest[\"options\"] everywhere outside normalize_quest(item).",
                "Replace quest[\"correct_choice\"] with quest[\"correct_option_text\"] or quest[\"correct_option_index\"] as appropriate.",
            ]
        )
    if validation_error.code == ROOT_FIRST_CONTENT_LOADING:
        guidance.append(
            "Do not read the root content file first. resolve_content_path() must iterate CONTENT_CANDIDATE_PATHS in outputs-first order."
        )
    if validation_error.code in {RESULT_FLOW_MISSING, BATTLE_FLOW_MISSING, CONTRACT_MISSING_MARKER}:
        guidance.append(
            "If a required screen constant or transition is missing, add the literal constant name and literal st.session_state.current_screen assignment."
        )
    if validation_error.code in {COACHING_FLOW_MISSING, INTERACTION_UNITS_RUNTIME_MISSING}:
        guidance.append(
            "For interaction-unit/coaching flows, read content['interaction_units'], keep current_screen transitions explicit, and implement api_chat_submit instead of quiz-style quest submission."
        )
    if validation_error.code == LEGACY_QUEST_RUNTIME_ACCESS:
        guidance.append(
            "Remove legacy content.get('quests') style access and drive runtime flow from interaction_units instead."
        )
    if validation_error.code == PYTHON_SYNTAX_INVALID:
        guidance.append("Fix Python syntax first, then preserve all required screen constants and transitions.")
    return json.dumps(guidance, ensure_ascii=False, indent=2)


def _extract_interface_screen_ids(interface_spec: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for screen_id in re.findall(r"\bS\d+\b", interface_spec):
        if screen_id in seen:
            continue
        seen.add(screen_id)
        ordered.append(screen_id)
    return ordered


def _classify_contract_issue(contract_item: str) -> str:
    if "interaction_units" in contract_item:
        return INTERACTION_UNITS_RUNTIME_MISSING
    if any(token in contract_item for token in ("SCREEN_INPUT", "SCREEN_FOLLOW_UP", "SCREEN_RESULT", "SCREEN_ERROR", "api_chat_submit")):
        return COACHING_FLOW_MISSING
    if "BATTLE" in contract_item:
        return BATTLE_FLOW_MISSING
    if any(token in contract_item for token in ("IMPROVEMENT_RESULT", "MULTIPLE_CHOICE_RESULT", "SESSION_RESULT")):
        return RESULT_FLOW_MISSING
    return CONTRACT_MISSING_MARKER


def _normalize_target_framework(value: str) -> str:
    normalized = (value or "streamlit").strip().lower()
    return normalized or "streamlit"


def _build_unsupported_reason(target_framework: str) -> str:
    if target_framework in KNOWN_UNSUPPORTED_TARGET_FRAMEWORKS:
        return (
            f"target_framework '{target_framework}' is not supported yet. "
            "Currently supported: streamlit"
        )

    known_values = ", ".join(sorted(KNOWN_TARGET_FRAMEWORKS))
    return (
        f"target_framework '{target_framework}' is not recognized. "
        f"Known values: {known_values}."
    )


def _normalize_grade_thresholds(
    service_grades: object,
    grade_levels: list[str],
) -> dict[str, dict[str, int | None]]:
    if not isinstance(service_grades, dict):
        return {}

    thresholds: dict[str, dict[str, int | None]] = {}
    for grade in grade_levels:
        raw_rule = service_grades.get(grade)
        min_score = 0
        max_score: int | None = None
        if isinstance(raw_rule, (list, tuple)) and raw_rule:
            first = raw_rule[0]
            second = raw_rule[1] if len(raw_rule) > 1 else None
            min_score = int(first) if first is not None else 0
            max_score = int(second) if second is not None else None
        thresholds[grade] = {
            "min_score": min_score,
            "max_score": max_score,
        }
    return thresholds


def _is_planning_package_dir(path: Path) -> bool:
    expected_files = {
        "constitution.md",
        "data_schema.json",
        "state_machine.md",
        "prompt_spec.md",
        "interface_spec.md",
    }
    return path.is_dir() and all((path / file_name).exists() for file_name in expected_files)
