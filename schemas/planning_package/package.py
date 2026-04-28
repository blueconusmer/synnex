from __future__ import annotations

from typing import Any

from pydantic import Field

from schemas.implementation.common import SchemaModel


class ServiceMeta(SchemaModel):
    """Top-level service metadata for a planning output package."""

    service_name: str = Field(description="Canonical service name for downstream loaders.")
    target_framework: str = Field(
        default="streamlit",
        description="Target application framework. Defaults to streamlit for compatibility.",
    )
    target_user: str = Field(description="Primary target learner or user segment.")
    purpose: str = Field(description="Service purpose or intended learning outcome.")
    version: str = Field(description="Planning package version string.")


class ContentSpec(SchemaModel):
    """Generic content generation specification."""

    content_types: list[str] = Field(description="Supported content types to generate.")
    total_count: int = Field(description="Total number of content items.")
    items_per_type: int = Field(description="Number of items for each content type.")
    difficulty_levels: list[str] = Field(description="Difficulty levels covered by the service.")


class EvaluationSpec(SchemaModel):
    """Generic evaluation and grading contract."""

    rubric_criteria: list[str] = Field(description="Evaluation rubric criteria.")
    grade_levels: list[str] = Field(description="Supported grade or proficiency levels.")
    score_rules: dict[str, Any] = Field(description="Flexible score calculation rules.")


class InteractionSpec(SchemaModel):
    """Generic interaction and state transition contract."""

    session_structure: list[str] = Field(description="Ordered learning session structure.")
    state_transitions: list[str] = Field(description="Supported interaction state transitions.")
    scoring_rules: dict[str, Any] = Field(description="Flexible interaction scoring rules.")


class InterfaceSpec(SchemaModel):
    """User-facing or integration-facing interface specification."""

    screens: list[str] = Field(description="Screens or views required by the service.")
    api_endpoints: list[str] = Field(description="API endpoints required by the service.")


class LLMSpec(SchemaModel):
    """Prompts required for generation and evaluation tasks."""

    generation_prompt: str = Field(description="Prompt template used for generation.")
    evaluation_prompt: str = Field(description="Prompt template used for evaluation.")


class TestSpec(SchemaModel):
    """Test and acceptance contract for the planned service."""

    test_file_path: str = Field(description="Primary automated test file path.")
    acceptance_criteria: list[str] = Field(description="Acceptance criteria for the service.")


class PlanningOutputPackage(SchemaModel):
    """Canonical generic planning output package schema."""

    service_meta: ServiceMeta = Field(description="Service metadata block.")
    content_spec: ContentSpec = Field(description="Content generation specification block.")
    evaluation_spec: EvaluationSpec = Field(description="Evaluation specification block.")
    interaction_spec: InteractionSpec = Field(description="Interaction specification block.")
    interface_spec: InterfaceSpec = Field(description="Interface specification block.")
    llm_spec: LLMSpec = Field(description="LLM prompt specification block.")
    test_spec: TestSpec = Field(description="Test specification block.")
    constraints: list[str] = Field(description="High-level implementation constraints.")


# Minimal compatibility alias for older imports.
PlanningPackage = PlanningOutputPackage
