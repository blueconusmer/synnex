"""Prototype builder agent for generating MVP application files."""

from __future__ import annotations

import ast
import json
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

from agents.implementation.helpers import dump_model, load_prompt_text, make_label


SUPPORTED_TARGET_FRAMEWORKS = {"streamlit"}
KNOWN_UNSUPPORTED_TARGET_FRAMEWORKS = {"react", "fastapi", "nextjs"}
KNOWN_TARGET_FRAMEWORKS = SUPPORTED_TARGET_FRAMEWORKS | KNOWN_UNSUPPORTED_TARGET_FRAMEWORKS
LLM_CALL_FAILED = "LLM_CALL_FAILED"
LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
FALLBACK_USED = "FALLBACK_USED"


class InvalidAppSourceError(ValueError):
    """Raised when the LLM app source does not satisfy minimal runtime constraints."""


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
    generation_inputs_summary = _build_generation_inputs_summary(input_model)
    builder_errors: list[str] = []
    fallback_used = False
    fallback_reason = ""
    generation_mode = "llm_generated"

    runtime_notes = [
        f"app.py는 outputs/{content_filename}을 읽는다.",
        "streamlit run app.py로 실행한다.",
    ]
    integration_notes = [
        f"{content_filename}이 outputs/ 아래에 존재해야 한다.",
    ]

    try:
        app_source, generation_notes = _generate_validated_app_source_with_llm(
            input_model=input_model,
            llm_client=llm_client,
            content_filename=content_filename,
        )
        runtime_notes.extend(generation_notes)
        runtime_notes.append("app.py는 LLM 생성 결과를 사용했다.")
    except InvalidAppSourceError as exc:
        builder_errors.extend([LLM_OUTPUT_INVALID, FALLBACK_USED])
        fallback_used = True
        fallback_reason = f"{LLM_OUTPUT_INVALID}: {exc}"
        generation_mode = "fallback_template"
        app_source = build_fallback_app_source(input_model)
        runtime_notes.append("LLM app.py 출력이 유효하지 않아 fallback template을 사용했다.")
    except Exception as exc:
        builder_errors.extend([LLM_CALL_FAILED, FALLBACK_USED])
        fallback_used = True
        fallback_reason = f"{LLM_CALL_FAILED}: {exc}"
        generation_mode = "fallback_template"
        app_source = build_fallback_app_source(input_model)
        runtime_notes.append("LLM app.py 생성 호출이 실패해 fallback template을 사용했다.")

    if _is_planning_package_dir(Path(spec.source_path)):
        runtime_notes.append("생성된 app.py는 Quest 세션 기반 화면(S0~S5)을 반영해야 한다.")
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
        reflection_attempts=0,
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
            screens=list(package.interface_spec.screens),
            api_endpoints=list(package.interface_spec.api_endpoints),
            score_rules=score_rules,
            grade_levels=grade_levels,
            grade_thresholds=grade_thresholds,
        )

    return build_streamlit_app_source(
        service_name=service_name,
        content_filename=content_filename,
    )


def _generate_app_source_with_llm(
    *,
    input_model: PrototypeBuilderInput,
    llm_client: LLMClient,
    content_filename: str,
) -> AppSourceGenerationOutput:
    prompt = _build_app_generation_prompt(
        input_model=input_model,
        content_filename=content_filename,
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
) -> tuple[str, list[str]]:
    generated_app = _generate_app_source_with_llm(
        input_model=input_model,
        llm_client=llm_client,
        content_filename=content_filename,
    )
    try:
        return (
            _validate_generated_app_source(
                generated_app=generated_app,
                content_filename=content_filename,
            ),
            list(generated_app.generation_notes),
        )
    except InvalidAppSourceError as first_error:
        repair_prompt = _build_app_validation_repair_prompt(
            input_model=input_model,
            content_filename=content_filename,
            invalid_source=generated_app.app_source,
            validation_error=str(first_error),
        )
        repaired_app = llm_client.generate_json(
            prompt=repair_prompt,
            response_model=AppSourceGenerationOutput,
            system_prompt=(
                "You fix one generated Streamlit app.py so it satisfies the runtime contract. "
                "Return JSON only. Do not call external LLM APIs."
            ),
        )
        repaired_source = _validate_generated_app_source(
            generated_app=repaired_app,
            content_filename=content_filename,
        )
        return (
            repaired_source,
            _dedupe_preserve_order(
                [
                    *generated_app.generation_notes,
                    "Initial app_source failed validation and was regenerated once.",
                    *repaired_app.generation_notes,
                ]
            ),
        )


def _build_app_generation_prompt(
    *,
    input_model: PrototypeBuilderInput,
    content_filename: str,
) -> str:
    spec = input_model.implementation_spec
    package_context = _load_package_prompt_context(Path(spec.source_path))
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
    )


def _build_app_validation_repair_prompt(
    *,
    input_model: PrototypeBuilderInput,
    content_filename: str,
    invalid_source: str,
    validation_error: str,
) -> str:
    spec = input_model.implementation_spec
    return (
        "The previous generated app.py failed validation.\n"
        f"Validation error: {validation_error}\n\n"
        "Regenerate the full app.py source while preserving the intended UI and behavior.\n"
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


def _validate_generated_app_source(
    *,
    generated_app: AppSourceGenerationOutput,
    content_filename: str,
) -> str:
    app_path = Path(generated_app.app_path or "app.py")
    if app_path.name != "app.py":
        raise InvalidAppSourceError("LLM output app_path must point to app.py.")

    app_source = _strip_python_fence(generated_app.app_source)
    if not app_source.strip():
        raise InvalidAppSourceError("LLM output app_source is empty.")
    if "st." not in app_source or "streamlit" not in app_source:
        raise InvalidAppSourceError("app_source does not appear to be a Streamlit app.")
    if content_filename not in app_source:
        raise InvalidAppSourceError(
            f"app_source does not reference required content file {content_filename}."
        )
    if not _references_outputs_content_path(app_source, content_filename):
        raise InvalidAppSourceError(
            f"app_source must reference outputs/{content_filename} as a content candidate."
        )
    if not _uses_outputs_before_root_fallback(app_source, content_filename):
        raise InvalidAppSourceError(
            "app_source must try outputs/{content_filename} before the root fallback file."
        )
    if not _has_missing_content_guidance(app_source):
        raise InvalidAppSourceError(
            "app_source must show user-facing guidance when the content file is missing."
        )
    if "st.experimental_rerun" in app_source:
        raise InvalidAppSourceError("app_source must use st.rerun() instead of st.experimental_rerun().")
    _validate_state_machine_contract(app_source)
    try:
        compile(app_source, "app.py", "exec")
    except SyntaxError as exc:
        raise InvalidAppSourceError(
            f"app_source is not valid Python: {exc.msg} at line {exc.lineno}."
        ) from exc
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
                f"app_source must not read planning package input at runtime: {forbidden}."
            )
    return app_source.rstrip() + "\n"


def _validate_state_machine_contract(app_source: str) -> None:
    required_markers = [
        "current_screen",
        "SCREEN_MULTIPLE_CHOICE_RESULT",
        "SCREEN_IMPROVEMENT_RESULT",
        "st.rerun()",
    ]
    for marker in required_markers:
        if marker not in app_source:
            raise InvalidAppSourceError(
                f"app_source must include state-machine marker: {marker}."
            )

    raw_field_patterns = [
        'quest["item_id"]',
        "quest['item_id']",
        'quest.get("item_id"',
        "quest.get('item_id'",
        'quest["choices"]',
        "quest['choices']",
        'quest.get("choices"',
        "quest.get('choices'",
    ]
    function_pairs = [
        ("api_quest_submit", "api_session_result"),
        ("render_multiple_choice_screen", "render_multiple_choice_result"),
        ("render_multiple_choice_result", "render_improvement_screen"),
        ("render_improvement_screen", "render_improvement_result"),
    ]
    for start_name, end_name in function_pairs:
        block = _extract_function_block(app_source, start_name, end_name)
        for pattern in raw_field_patterns:
            if pattern in block:
                raise InvalidAppSourceError(
                    f"{start_name} must use normalized quest fields only; found raw field reference {pattern}."
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
                f"{function_name} call passes {positional_count} positional args "
                f"but function defines {max_count}."
            )
        if provided_count < required_count:
            raise InvalidAppSourceError(
                f"{function_name} call provides {provided_count} args "
                f"but function requires {required_count}."
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


def _extract_function_block(app_source: str, start_name: str, end_name: str) -> str:
    start_marker = f"def {start_name}"
    end_marker = f"def {end_name}"
    if start_marker not in app_source or end_marker not in app_source:
        raise InvalidAppSourceError(
            f"app_source must include function block {start_name} before {end_name}."
        )
    return app_source.split(start_marker, 1)[1].split(end_marker, 1)[0]


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


def _build_generation_inputs_summary(input_model: PrototypeBuilderInput) -> list[str]:
    spec = input_model.implementation_spec
    summary = [
        f"target_framework={spec.target_framework}",
        f"service_purpose={'present' if spec.service_purpose else 'missing'}",
        f"target_user_count={len(spec.target_users)}",
        f"mvp_scope_count={len(spec.core_features)}",
        f"interaction_mode={input_model.content_interaction_output.interaction_mode}",
        f"interaction_unit_count={len(input_model.content_interaction_output.interaction_units)}",
        "spec_intake_output",
        "requirement_mapping_output",
        "content_interaction_output",
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
