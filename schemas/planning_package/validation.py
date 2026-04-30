from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field

from schemas.implementation.common import SchemaModel
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.planning_package.package import PlanningOutputPackage


class ValidationStatus(str, Enum):
    PASS = "PASS"
    AUTO_FIXED = "AUTO_FIXED"
    NEEDS_PLANNING_REVIEW = "NEEDS_PLANNING_REVIEW"
    FAIL = "FAIL"


class ValidationIssue(SchemaModel):
    code: str = Field(description="Stable issue code.")
    message: str = Field(description="Human-readable validation message.")
    field_path: str = Field(default="", description="Related package or runtime field path.")
    status: ValidationStatus = Field(description="Status classification for this issue.")


class AutoFixRecord(SchemaModel):
    field_path: str = Field(description="Field or runtime value that was normalized.")
    before: Any = Field(default=None, description="Original value before normalization.")
    after: Any = Field(default=None, description="Normalized value after correction.")
    reason: str = Field(description="Why this normalization is allowed.")


class PlanningReviewItem(SchemaModel):
    field_path: str = Field(description="Field that needs planning-team review.")
    reason: str = Field(description="Why this cannot be safely auto-fixed.")
    blocking: bool = Field(
        default=False,
        description="Whether this should block in a future strict mode.",
    )


class LLMQualityJudgement(SchemaModel):
    auto_fixable_functional_gaps: list[str] = Field(default_factory=list)
    planning_review_required: list[str] = Field(default_factory=list)
    blocking_conflicts: list[str] = Field(default_factory=list)
    mvp_implementation_sufficient: bool = Field(default=True)
    summary: str = Field(default="")


class ContentDistribution(SchemaModel):
    item_count_by_type: dict[str, int] = Field(default_factory=dict)
    total_count: int = Field(default=0)
    distribution_source: str = Field(default="")


class InputRuntimeConfig(SchemaModel):
    service_slug: str = Field(default="")
    target_framework: str = Field(default="streamlit")
    content_output_filename: str = Field(default="")
    normalized_source_path: str = Field(default="")
    service_name_source: str = Field(default="")
    content_types_source: str = Field(default="")
    total_count_source: str = Field(default="")
    screens_source: str = Field(default="")
    api_endpoints_source: str = Field(default="")
    content_distribution: ContentDistribution = Field(default_factory=ContentDistribution)


class InputIntakeResult(SchemaModel):
    status: ValidationStatus = Field(description="Overall input intake status.")
    planning_package: PlanningOutputPackage | None = Field(default=None)
    implementation_spec: ImplementationSpec | None = Field(default=None)
    source_paths: list[str] = Field(default_factory=list)
    runtime_config: InputRuntimeConfig | None = Field(default=None)
    auto_fixes: list[AutoFixRecord] = Field(default_factory=list)
    planning_review_items: list[PlanningReviewItem] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    quality_judgement: LLMQualityJudgement | None = Field(default=None)
