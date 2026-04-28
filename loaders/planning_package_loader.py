from __future__ import annotations

import json
import re
from pathlib import Path

from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.planning_package import (
    ContentSpec,
    EvaluationSpec,
    InputIntakeResult,
    InteractionSpec,
    InterfaceSpec,
    LLMSpec,
    PlanningOutputPackage,
    ServiceMeta,
    TestSpec,
)
from validators import (
    DeterministicInputQualityJudge,
    InputQualityJudge,
    build_failed_input_intake_result,
    validate_and_normalize_planning_package,
)


REQUIRED_FILES = {
    "constitution": "constitution.md",
    "data_schema": "data_schema.json",
    "state_machine": "state_machine.md",
    "prompt_spec": "prompt_spec.md",
    "interface_spec": "interface_spec.md",
}
OPTIONAL_FILES = {
    "pytest_file": "pytest.py",
}
EXPECTED_FILES = {**REQUIRED_FILES, **OPTIONAL_FILES}


class PlanningPackageLoadError(ValueError):
    """Raised when a planning package file exists but cannot be parsed."""


def load_planning_package(package_dir: Path) -> PlanningOutputPackage:
    """Load a planning package into the canonical PlanningOutputPackage schema."""

    if not package_dir.exists() or not package_dir.is_dir():
        raise FileNotFoundError(f"Planning package directory does not exist: {package_dir}")

    paths = {key: package_dir / filename for key, filename in EXPECTED_FILES.items()}
    missing_files = [
        str(package_dir / filename)
        for filename in REQUIRED_FILES.values()
        if not (package_dir / filename).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            "Planning package is missing required files: " + ", ".join(missing_files)
        )

    constitution_text = _read_text(paths["constitution"])
    data_schema = _read_json(paths["data_schema"])
    state_machine_text = _read_text(paths["state_machine"])
    prompt_spec_text = _read_text(paths["prompt_spec"])
    interface_spec_text = _read_text(paths["interface_spec"])
    pytest_path = paths["pytest_file"]
    pytest_text = _read_text(pytest_path) if pytest_path.exists() else ""

    constitution_sections = _parse_markdown_sections(constitution_text)
    state_machine_sections = _parse_markdown_sections(state_machine_text)
    interface_sections = _parse_markdown_sections(interface_spec_text)
    prompt_sections = _parse_markdown_sections(prompt_spec_text)

    service_name, version = _split_service_slug(package_dir.name)
    score_rules = _build_score_rules(constitution_text, data_schema)
    interaction_scoring_rules = _build_interaction_scoring_rules(
        constitution_text,
        data_schema,
        state_machine_text,
    )

    return PlanningOutputPackage(
        service_meta=ServiceMeta(
            service_name=service_name,
            target_user=_extract_target_user(constitution_text),
            purpose=_build_service_purpose(constitution_sections),
            version=version,
        ),
        content_spec=ContentSpec(
            content_types=_extract_content_types(data_schema),
            total_count=_extract_total_count(data_schema),
            items_per_type=_extract_items_per_type(data_schema),
            difficulty_levels=_extract_difficulty_levels(data_schema),
        ),
        evaluation_spec=EvaluationSpec(
            rubric_criteria=_extract_rubric_criteria(constitution_text),
            grade_levels=["브론즈", "실버", "골드", "플래티넘"],
            score_rules=score_rules,
        ),
        interaction_spec=InteractionSpec(
            session_structure=_extract_session_structure(state_machine_text),
            state_transitions=_extract_state_transitions(state_machine_text),
            scoring_rules=interaction_scoring_rules,
        ),
        interface_spec=InterfaceSpec(
            screens=_extract_screens(interface_sections),
            api_endpoints=_extract_api_endpoints(interface_spec_text),
        ),
        llm_spec=LLMSpec(
            generation_prompt=_extract_generation_prompt(prompt_spec_text, prompt_sections),
            evaluation_prompt=_extract_evaluation_prompt(prompt_spec_text, prompt_sections),
        ),
        test_spec=TestSpec(
            test_file_path=EXPECTED_FILES["pytest_file"] if pytest_path.exists() else "",
            acceptance_criteria=_extract_acceptance_criteria(pytest_text),
        ),
        constraints=_extract_constraints(constitution_sections),
    )


def load_input_intake(
    package_dir: Path,
    quality_judge: InputQualityJudge | None = None,
) -> InputIntakeResult:
    """Load, validate, and normalize a planning package before the 6-agent pipeline."""

    try:
        package = load_planning_package(package_dir)
        implementation_spec = planning_package_to_implementation_spec(package, package_dir)
    except FileNotFoundError as exc:
        return build_failed_input_intake_result(
            package_dir=package_dir,
            message=str(exc),
            code="PLANNING_PACKAGE_FILE_MISSING",
        )
    except PlanningPackageLoadError as exc:
        return build_failed_input_intake_result(
            package_dir=package_dir,
            message=str(exc),
            code="PLANNING_PACKAGE_PARSE_FAILED",
        )

    return validate_and_normalize_planning_package(
        package=package,
        package_dir=package_dir,
        implementation_spec=implementation_spec,
        quality_judge=quality_judge or DeterministicInputQualityJudge(),
    )


def planning_package_to_implementation_spec(
    package: PlanningOutputPackage,
    package_dir: Path,
) -> ImplementationSpec:
    """Adapt a PlanningOutputPackage into the current implementation pipeline input schema."""

    target_users = [package.service_meta.target_user] if package.service_meta.target_user else []

    return ImplementationSpec(
        source_path=str(package_dir),
        service_name=package.service_meta.service_name,
        target_framework=package.service_meta.target_framework or "streamlit",
        service_purpose=package.service_meta.purpose,
        target_users=target_users,
        learning_goals=package.evaluation_spec.rubric_criteria,
        core_features=package.content_spec.content_types,
        total_count=package.content_spec.total_count,
        items_per_type=package.content_spec.items_per_type,
        content_interaction_direction=(
            package.interaction_spec.session_structure
            + package.interaction_spec.state_transitions
        ),
        excluded_scope=[],
        expected_outputs=package.interface_spec.screens + package.interface_spec.api_endpoints,
        acceptance_criteria=package.test_spec.acceptance_criteria,
        constraints=package.constraints,
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise PlanningPackageLoadError(f"Failed to parse JSON file: {path}") from exc
    return payload if isinstance(payload, dict) else {}


def _split_service_slug(directory_name: str) -> tuple[str, str]:
    match = re.match(r"^(?P<name>.+?)(?:[_-](?P<version>v\d+(?:\.\d+)*))?$", directory_name)
    if not match:
        return directory_name, ""
    return match.group("name") or directory_name, match.group("version") or ""


def _parse_markdown_sections(text: str) -> dict[str, list[str]]:
    current_section: str | None = None
    sections: dict[str, list[str]] = {}
    for line in text.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections.setdefault(current_section, [])
            continue
        if current_section is not None:
            sections[current_section].append(line.rstrip())
    return sections


def _find_section_lines(sections: dict[str, list[str]], query: str) -> list[str]:
    for title, lines in sections.items():
        if query in title:
            return lines
    return []


def _clean_bullet(text: str) -> str:
    return re.sub(r"^(?:[-*]|\d+\.)\s*", "", text).strip()


def _extract_target_user(text: str) -> str:
    return "중학생" if "중학생" in text else ""


def _build_service_purpose(sections: dict[str, list[str]]) -> str:
    problem_text = _section_text(sections, "교육공학적 문제 재정의")
    objective_text = _section_text(sections, "학습 목표")
    return " ".join(part for part in [problem_text, objective_text] if part).strip()


def _section_text(sections: dict[str, list[str]], query: str) -> str:
    lines = _find_section_lines(sections, query)
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if stripped.startswith("|"):
            continue
        cleaned_line = _clean_bullet(stripped).strip("> ").strip()
        if cleaned_line:
            cleaned.append(cleaned_line)
    return " ".join(cleaned).strip()


def _extract_rubric_criteria(text: str) -> list[str]:
    sections = _parse_markdown_sections(text)
    rubric_lines: list[str] = []
    for title, lines in sections.items():
        if "평가" in title and "루브릭" in title:
            rubric_lines = lines
            break
    if not rubric_lines:
        rubric_lines = _find_rubric_table_lines(text)

    criteria: list[str] = []
    for line in rubric_lines:
        stripped = line.strip()
        if stripped.startswith("| **"):
            match = re.search(r"\*\*(.+?)\*\*", line)
            if match:
                criterion = match.group(1).strip()
                if criterion not in {"우수", "양호", "미흡"}:
                    criteria.append(criterion)
    return criteria


def _find_rubric_table_lines(text: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if not all(token in stripped for token in ["기준", "우수", "양호", "미흡"]):
            continue

        table_lines: list[str] = []
        for table_line in lines[index + 1 :]:
            if not table_line.strip().startswith("|"):
                break
            table_lines.append(table_line)
        return table_lines
    return []


def _extract_service_grades(text: str) -> dict[str, list[int | None]]:
    grades: dict[str, list[int | None]] = {}
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        parts = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(parts) != 2:
            continue
        grade, score_range = parts
        if grade not in {"브론즈", "실버", "골드", "플래티넘"}:
            continue
        numbers = [int(num) for num in re.findall(r"\d+", score_range)]
        if "이상" in score_range:
            grades[grade] = [numbers[0], None] if numbers else [0, None]
        elif len(numbers) >= 2:
            grades[grade] = [numbers[0], numbers[1]]
    return grades


def _extract_answer_score_rules(data_schema: dict) -> dict:
    return (
        data_schema.get("definitions", {})
        .get("Answer", {})
        .get("fields", {})
        .get("earned_score", {})
        .get("rules", {})
    ) or {}


def _extract_rubric_overall_rule(data_schema: dict) -> str:
    return (
        data_schema.get("definitions", {})
        .get("RubricResult", {})
        .get("fields", {})
        .get("overall", {})
        .get("description", "")
    ) or ""


def _build_score_rules(constitution_text: str, data_schema: dict) -> dict:
    return {
        "rubric_grades": ["우수", "양호", "미흡"],
        "service_grades": _extract_service_grades(constitution_text),
        "answer_score_rules": _extract_answer_score_rules(data_schema),
    }


def _build_interaction_scoring_rules(
    constitution_text: str,
    data_schema: dict,
    state_machine_text: str,
) -> dict:
    session_completion = (
        "3개 퀘스트 모두 제출 완료 시 세션 결과 화면 표시"
        if "3개 퀘스트 모두 제출 완료" in constitution_text
        else ""
    )
    grade_up_message = (
        "축하해요! 이제 [등급] 단계예요"
        if "축하해요! 이제 [등급] 단계예요" in constitution_text
        else ""
    )

    return {
        "answer_score_rules": _extract_answer_score_rules(data_schema),
        "rubric_overall_rule": _extract_rubric_overall_rule(data_schema),
        "session_completion_rule": session_completion,
        "grade_up_message_rule": grade_up_message,
        "llm_timeout_message": (
            "잠시 후 다시 시도해주세요"
            if "E_LLM_TIMEOUT" in state_machine_text
            else ""
        ),
    }


def _extract_content_types(data_schema: dict) -> list[str]:
    return (
        data_schema.get("definitions", {})
        .get("Quest", {})
        .get("fields", {})
        .get("quest_type", {})
        .get("values", [])
    ) or []


def _extract_total_count(data_schema: dict) -> int:
    session_fields = (
        data_schema.get("definitions", {})
        .get("Session", {})
        .get("fields", {})
        .get("quest_ids", {})
    )
    min_length = session_fields.get("min_length")
    max_length = session_fields.get("max_length")
    if min_length == max_length and isinstance(min_length, int):
        return min_length
    return 0


def _extract_items_per_type(data_schema: dict) -> int:
    composition = (
        data_schema.get("constraints", {}).get("session_composition", "")
        or data_schema.get("definitions", {})
        .get("Session", {})
        .get("description", "")
    )
    bracket_match = re.search(r"\[(.+?)\]", composition)
    if bracket_match:
        segments = [part.strip() for part in bracket_match.group(1).split(",")]
        main_count = sum(1 for segment in segments if segment == "main")
        if main_count:
            return main_count

    main_count_match = re.search(r"main(?:\s*난이도)?\s*(\d+)개", composition)
    if main_count_match:
        return int(main_count_match.group(1))
    return 0


def _extract_difficulty_levels(data_schema: dict) -> list[str]:
    return (
        data_schema.get("definitions", {})
        .get("Quest", {})
        .get("fields", {})
        .get("difficulty", {})
        .get("values", [])
    ) or []


def _extract_session_structure(text: str) -> list[str]:
    matches = re.findall(r"\[(SESSION_START|QUEST_\d+_(?:ACTIVE|FEEDBACK)|SESSION_COMPLETED)\]", text)
    return matches or []


def _extract_state_transitions(text: str) -> list[str]:
    states = _extract_session_structure(text)
    return [f"{current}->{next_state}" for current, next_state in zip(states, states[1:])]


def _extract_screens(sections: dict[str, list[str]]) -> list[str]:
    lines = _find_section_lines(sections, "화면 구성 개요")
    screens: list[str] = []
    for line in lines:
        matches = re.findall(r"`(S\d+)`", line)
        screens.extend(matches)
    return screens


def _extract_api_endpoints(text: str) -> list[str]:
    endpoints = re.findall(r"\*\*Endpoint\*\*:\s*`(?:[A-Z]+)\s+([^`]+)`", text)
    return [endpoint.split("?")[0] for endpoint in endpoints] if endpoints else []


def _extract_generation_prompt(text: str, sections: dict[str, list[str]]) -> str:
    intro_prompt = _extract_code_block_after_heading(text, "### 1.1. 객관식 퀘스트 생성 (intro)")
    main_prompt = _extract_code_block_after_heading(text, "### 1.2. 질문 개선형 퀘스트 생성 (main)")
    prompts = [prompt for prompt in [intro_prompt, main_prompt] if prompt]
    if prompts:
        return "\n\n".join(prompts)
    return _section_text(sections, "퀘스트 생성 프롬프트")


def _extract_evaluation_prompt(text: str, sections: dict[str, list[str]]) -> str:
    prompt = _extract_code_block_after_heading(text, "### 2.1. 질문 개선형 답변 평가")
    if prompt:
        return prompt
    return _section_text(sections, "답변 평가 프롬프트")


def _extract_code_block_after_heading(text: str, heading: str) -> str:
    pattern = re.escape(heading) + r".*?#### System Prompt\s*```(?:\w+)?\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_acceptance_criteria(pytest_text: str) -> list[str]:
    lines = pytest_text.splitlines()
    criteria: list[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        if "테스트 그룹:" in stripped:
            collecting = True
            continue
        if collecting and re.match(r"^\d+\.\s+", stripped):
            criteria.append(re.sub(r"^\d+\.\s*", "", stripped))
            continue
        if collecting and stripped == "":
            break

    return criteria


def _extract_constraints(sections: dict[str, list[str]]) -> list[str]:
    constraints: list[str] = []
    for query in ["서비스 전체 설계 원칙", "우선순위 원칙"]:
        for line in _find_section_lines(sections, query):
            stripped = line.strip()
            if not stripped or stripped == "---" or stripped.startswith("|"):
                continue
            cleaned = _clean_bullet(stripped).strip("> ").strip()
            if cleaned:
                constraints.append(cleaned)
    return constraints
