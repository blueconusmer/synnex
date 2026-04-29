from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from orchestrator.app_source import build_content_filename
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.planning_package import PlanningOutputPackage
from schemas.planning_package.validation import (
    AutoFixRecord,
    ContentDistribution,
    InputIntakeResult,
    InputRuntimeConfig,
    LLMQualityJudgement,
    PlanningReviewItem,
    ValidationIssue,
    ValidationStatus,
)


class InputQualityJudge(Protocol):
    def judge(
        self,
        *,
        package: PlanningOutputPackage,
        implementation_spec: ImplementationSpec,
        runtime_config: InputRuntimeConfig,
        issues: list[ValidationIssue],
        planning_review_items: list[PlanningReviewItem],
        auto_fixes: list[AutoFixRecord],
    ) -> LLMQualityJudgement:
        """Classify input quality without mutating the package."""


class DeterministicInputQualityJudge:
    """Rule-based stand-in for the future LLM quality gate."""

    def judge(
        self,
        *,
        package: PlanningOutputPackage,
        implementation_spec: ImplementationSpec,
        runtime_config: InputRuntimeConfig,
        issues: list[ValidationIssue],
        planning_review_items: list[PlanningReviewItem],
        auto_fixes: list[AutoFixRecord],
    ) -> LLMQualityJudgement:
        _ = package
        _ = implementation_spec
        blocking_conflicts = [
            issue.message for issue in issues if issue.status == ValidationStatus.FAIL
        ]
        return LLMQualityJudgement(
            auto_fixable_functional_gaps=[fix.reason for fix in auto_fixes],
            planning_review_required=[item.reason for item in planning_review_items],
            blocking_conflicts=blocking_conflicts,
            mvp_implementation_sufficient=not blocking_conflicts,
            summary=_build_judgement_summary(
                auto_fix_count=len(auto_fixes),
                review_count=len(planning_review_items),
                fail_count=len(blocking_conflicts),
            ),
        )


def validate_and_normalize_planning_package(
    *,
    package: PlanningOutputPackage,
    package_dir: Path,
    implementation_spec: ImplementationSpec,
    quality_judge: InputQualityJudge | None = None,
) -> InputIntakeResult:
    auto_fixes: list[AutoFixRecord] = []
    issues: list[ValidationIssue] = []
    planning_review_items: list[PlanningReviewItem] = []

    service_slug = _slugify_service_name(package.service_meta.service_name)
    if service_slug != package.service_meta.service_name:
        auto_fixes.append(
            AutoFixRecord(
                field_path="runtime_config.service_slug",
                before=package.service_meta.service_name,
                after=service_slug,
                reason="service_name을 파일명에 안전한 service_slug로 정규화했다.",
            )
        )
    else:
        auto_fixes.append(
            AutoFixRecord(
                field_path="runtime_config.service_slug",
                before=None,
                after=service_slug,
                reason="service_slug 실행 값을 생성했다.",
            )
        )

    target_framework = implementation_spec.target_framework or "streamlit"
    auto_fixes.append(
        AutoFixRecord(
            field_path="runtime_config.target_framework",
            before=None,
            after=target_framework,
            reason="ImplementationSpec 기준 target_framework 실행 값을 기록했다.",
        )
    )

    content_output_filename = build_content_filename(service_slug)
    auto_fixes.append(
        AutoFixRecord(
            field_path="runtime_config.content_output_filename",
            before=None,
            after=content_output_filename,
            reason="service_slug 기반 콘텐츠 출력 파일명을 생성했다.",
        )
    )

    normalized_source_path = _workspace_neutral_path(package_dir)
    auto_fixes.append(
        AutoFixRecord(
            field_path="runtime_config.normalized_source_path",
            before=str(package_dir),
            after=normalized_source_path,
            reason="입력 package 경로를 절대 경로로 정규화했다.",
        )
    )

    content_distribution = _infer_content_distribution(
        package=package,
        package_dir=package_dir,
    )
    if content_distribution.item_count_by_type:
        auto_fixes.append(
            AutoFixRecord(
                field_path="runtime_config.content_distribution",
                before=None,
                after=content_distribution.model_dump(mode="json"),
                reason="생성 단위 수를 content type별 분포로 추론했다.",
            )
        )

    runtime_config = InputRuntimeConfig(
        service_slug=service_slug,
        target_framework=target_framework,
        content_output_filename=content_output_filename,
        normalized_source_path=normalized_source_path,
        content_distribution=content_distribution,
    )

    _validate_required_structure(package, issues)
    _validate_generation_units(package, content_distribution, issues)
    _collect_optional_defaults(package, auto_fixes)
    _collect_planning_review_items(package, planning_review_items)

    judge = quality_judge or DeterministicInputQualityJudge()
    quality_judgement = judge.judge(
        package=package,
        implementation_spec=implementation_spec,
        runtime_config=runtime_config,
        issues=issues,
        planning_review_items=planning_review_items,
        auto_fixes=auto_fixes,
    )

    status = _resolve_status(
        issues=issues,
        planning_review_items=planning_review_items,
        auto_fixes=auto_fixes,
    )
    return InputIntakeResult(
        status=status,
        planning_package=package,
        implementation_spec=implementation_spec,
        source_paths=_expected_source_paths(package_dir),
        runtime_config=runtime_config,
        auto_fixes=auto_fixes,
        planning_review_items=planning_review_items,
        issues=issues,
        quality_judgement=quality_judgement,
    )


def build_failed_input_intake_result(
    *,
    package_dir: Path,
    message: str,
    code: str,
) -> InputIntakeResult:
    issue = ValidationIssue(
        code=code,
        message=message,
        field_path=str(package_dir),
        status=ValidationStatus.FAIL,
    )
    runtime_config = InputRuntimeConfig(
        service_slug=_slugify_service_name(package_dir.name),
        target_framework="streamlit",
        content_output_filename=build_content_filename(_slugify_service_name(package_dir.name)),
        normalized_source_path=_workspace_neutral_path(package_dir),
    )
    return InputIntakeResult(
        status=ValidationStatus.FAIL,
        source_paths=_expected_source_paths(package_dir),
        runtime_config=runtime_config,
        issues=[issue],
        quality_judgement=LLMQualityJudgement(
            blocking_conflicts=[message],
            mvp_implementation_sufficient=False,
            summary=f"Input intake failed: {message}",
        ),
    )


def _validate_required_structure(
    package: PlanningOutputPackage,
    issues: list[ValidationIssue],
) -> None:
    required_checks = [
        ("content_spec.content_types", package.content_spec.content_types),
        ("content_spec.total_count", package.content_spec.total_count),
        ("evaluation_spec.rubric_criteria", package.evaluation_spec.rubric_criteria),
        ("interaction_spec.session_structure", package.interaction_spec.session_structure),
        ("interface_spec.screens", package.interface_spec.screens),
    ]
    for field_path, value in required_checks:
        if value:
            continue
        issues.append(
            ValidationIssue(
                code="REQUIRED_STRUCTURE_MISSING",
                message=f"필수 실행 구조가 비어 있습니다: {field_path}",
                field_path=field_path,
                status=ValidationStatus.FAIL,
            )
        )


def _validate_generation_units(
    package: PlanningOutputPackage,
    content_distribution: ContentDistribution,
    issues: list[ValidationIssue],
) -> None:
    if package.content_spec.total_count <= 0:
        issues.append(
            ValidationIssue(
                code="CONTENT_TOTAL_COUNT_MISSING",
                message="서비스별 생성 단위 총수가 1 이상이어야 합니다.",
                field_path="content_spec.total_count",
                status=ValidationStatus.FAIL,
            )
        )
    if not content_distribution.item_count_by_type:
        issues.append(
            ValidationIssue(
                code="CONTENT_DISTRIBUTION_MISSING",
                message="content type별 생성 단위 분포를 추론할 수 없습니다.",
                field_path="runtime_config.content_distribution",
                status=ValidationStatus.FAIL,
            )
        )
        return
    if content_distribution.total_count != package.content_spec.total_count:
        issues.append(
            ValidationIssue(
                code="CONTENT_DISTRIBUTION_MISMATCH",
                message="content distribution 합계가 content_spec.total_count와 다릅니다.",
                field_path="runtime_config.content_distribution",
                status=ValidationStatus.FAIL,
            )
        )


def _collect_optional_defaults(
    package: PlanningOutputPackage,
    auto_fixes: list[AutoFixRecord],
) -> None:
    optional_fields = [
        ("service_meta.target_user", package.service_meta.target_user, ""),
        ("llm_spec.evaluation_prompt", package.llm_spec.evaluation_prompt, ""),
        ("test_spec.acceptance_criteria", package.test_spec.acceptance_criteria, []),
        ("constraints", package.constraints, []),
    ]
    for field_path, value, default_value in optional_fields:
        if value:
            continue
        auto_fixes.append(
            AutoFixRecord(
                field_path=field_path,
                before=value,
                after=default_value,
                reason=f"optional field 누락을 기본값으로 처리했다: {field_path}",
            )
        )


def _collect_planning_review_items(
    package: PlanningOutputPackage,
    planning_review_items: list[PlanningReviewItem],
) -> None:
    if not package.llm_spec.generation_prompt:
        planning_review_items.append(
            PlanningReviewItem(
                field_path="llm_spec.generation_prompt",
                reason="콘텐츠 생성 의도와 표현을 담은 generation prompt는 자동 작성하지 않는다.",
            )
        )
    if not package.service_meta.purpose:
        planning_review_items.append(
            PlanningReviewItem(
                field_path="service_meta.purpose",
                reason="서비스 목적은 학습 경험과 의도를 바꾸는 영역이라 자동 작성하지 않는다.",
            )
        )


def _infer_content_distribution(
    *,
    package: PlanningOutputPackage,
    package_dir: Path,
) -> ContentDistribution:
    data_schema_path = package_dir / "data_schema.json"
    try:
        data_schema = json.loads(data_schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data_schema = {}

    content_types = package.content_spec.content_types
    composition = (
        data_schema.get("constraints", {}).get("session_composition", "")
        or data_schema.get("definitions", {})
        .get("Session", {})
        .get("description", "")
    )
    explicit_counts = _extract_explicit_type_counts(
        composition=composition,
        content_types=content_types,
    )
    if explicit_counts:
        return ContentDistribution(
            item_count_by_type=explicit_counts,
            total_count=sum(explicit_counts.values()),
            distribution_source="data_schema.session_composition",
        )

    quest_sequence_description = (
        data_schema.get("definitions", {})
        .get("Session", {})
        .get("fields", {})
        .get("quest_sequence", {})
        .get("description", "")
    )
    explicit_counts = _extract_explicit_type_counts(
        composition=quest_sequence_description,
        content_types=content_types,
    )
    if explicit_counts:
        return ContentDistribution(
            item_count_by_type=explicit_counts,
            total_count=sum(explicit_counts.values()),
            distribution_source="data_schema.session.quest_sequence",
        )

    bracket_match = re.search(r"\[(.+?)\]", composition)
    if bracket_match and len(content_types) >= 2:
        segments = [part.strip() for part in bracket_match.group(1).split(",")]
        difficulty_to_type = {
            "intro": content_types[0],
            "main": content_types[1],
        }
        counts: dict[str, int] = {content_type: 0 for content_type in content_types}
        for segment in segments:
            content_type = difficulty_to_type.get(segment)
            if content_type:
                counts[content_type] += 1
        counts = {key: value for key, value in counts.items() if value > 0}
        if counts:
            return ContentDistribution(
                item_count_by_type=counts,
                total_count=sum(counts.values()),
                distribution_source="data_schema.session_composition",
            )

    if len(content_types) == 2 and 0 < package.content_spec.items_per_type < package.content_spec.total_count:
        counts = {
            content_types[0]: package.content_spec.total_count - package.content_spec.items_per_type,
            content_types[1]: package.content_spec.items_per_type,
        }
        return ContentDistribution(
            item_count_by_type=counts,
            total_count=sum(counts.values()),
            distribution_source="content_spec.items_per_type",
        )

    if content_types and package.content_spec.total_count > 0:
        counts = {content_type: 0 for content_type in content_types}
        for index in range(package.content_spec.total_count):
            counts[content_types[index % len(content_types)]] += 1
        return ContentDistribution(
            item_count_by_type=counts,
            total_count=sum(counts.values()),
            distribution_source="round_robin_fallback",
        )

    return ContentDistribution()


def _extract_explicit_type_counts(
    *,
    composition: str,
    content_types: list[str],
) -> dict[str, int]:
    if not composition or not content_types:
        return {}

    allowed = set(content_types)
    counts: dict[str, int] = {}
    bracket_match = re.search(r"\[(.+?)\]", composition)
    raw_values = bracket_match.group(1) if bracket_match else composition
    parts = [part.strip() for part in raw_values.split(",") if part.strip()]

    alias_map = {
        "situationcardadvanced": "situation_card",
        "situation_card_advanced": "situation_card",
        "multiplechoice": "multiple_choice",
        "multiple_choice": "multiple_choice",
        "questionimprovement": "question_improvement",
        "question_improvement": "question_improvement",
        "situationcard": "situation_card",
        "situation_card": "situation_card",
    }

    for part in parts:
        normalized = re.sub(r"[^a-z0-9_]+", "", part.lower())
        normalized = alias_map.get(normalized, normalized)

        if normalized in allowed:
            counts[normalized] = counts.get(normalized, 0) + 1

    return counts


def _resolve_status(
    *,
    issues: list[ValidationIssue],
    planning_review_items: list[PlanningReviewItem],
    auto_fixes: list[AutoFixRecord],
) -> ValidationStatus:
    if any(issue.status == ValidationStatus.FAIL for issue in issues):
        return ValidationStatus.FAIL
    if planning_review_items:
        return ValidationStatus.NEEDS_PLANNING_REVIEW
    if auto_fixes:
        return ValidationStatus.AUTO_FIXED
    return ValidationStatus.PASS


def _expected_source_paths(package_dir: Path) -> list[str]:
    filenames = [
        "constitution.md",
        "data_schema.json",
        "state_machine.md",
        "prompt_spec.md",
        "interface_spec.md",
    ]
    paths = [_workspace_neutral_path(package_dir / filename) for filename in filenames]
    optional_pytest = package_dir / "pytest.py"
    if optional_pytest.exists():
        paths.append(_workspace_neutral_path(optional_pytest))
    return paths


def _workspace_neutral_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _slugify_service_name(value: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z가-힣_]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "service_output"


def _build_judgement_summary(
    *,
    auto_fix_count: int,
    review_count: int,
    fail_count: int,
) -> str:
    if fail_count:
        return f"{fail_count}개 실행 불가 입력 충돌이 있습니다."
    if review_count:
        return f"{review_count}개 기획팀 검토 항목이 있으며 경고로 기록하고 진행합니다."
    if auto_fix_count:
        return f"{auto_fix_count}개 기능적 누락을 코드 기반으로 보완했습니다."
    return "입력 품질 검사를 통과했습니다."
