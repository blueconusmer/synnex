from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import AgentLabel, GeneratedFile, SchemaModel
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput


class PrototypeBuilderInput(SchemaModel):
    spec_intake_output: SpecIntakeOutput = Field(
        description="Structured intake output for the current service."
    )
    requirement_mapping_output: RequirementMappingOutput = Field(
        description="Requirement mapping output for app-level constraints."
    )
    content_interaction_output: ContentInteractionOutput = Field(
        description="Generated content and interaction data for the MVP."
    )
    implementation_spec: ImplementationSpec = Field(
        description="Runtime implementation configuration for the current service."
    )


class AppSourceGenerationOutput(SchemaModel):
    app_path: str = Field(
        default="app.py",
        description="Relative app file path. For Streamlit MVPs this must be app.py.",
    )
    app_source: str = Field(description="Full generated Python source for app.py.")
    generation_notes: list[str] = Field(
        default_factory=list,
        description="Short notes explaining the generated app structure.",
    )


class PrototypeBuilderOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    service_name: str = Field(description="Service name for the generated MVP.")
    target_framework: str = Field(
        default="streamlit",
        description="Framework requested by the implementation spec.",
    )
    is_supported: bool = Field(
        default=True,
        description="Whether the requested target framework can be generated now.",
    )
    unsupported_reason: str = Field(
        default="",
        description="Reason why the requested target framework is not generated.",
    )
    app_entrypoint: str = Field(description="Relative path to the generated app.")
    generated_files: list[GeneratedFile] = Field(
        default_factory=list,
        description="Files that should be materialized for the MVP.",
    )
    runtime_notes: list[str] = Field(
        default_factory=list,
        description="Instructions or notes for runtime execution.",
    )
    integration_notes: list[str] = Field(
        default_factory=list,
        description="Notes for downstream test and QA stages.",
    )
    generation_mode: str = Field(
        default="llm_generated",
        description="How app.py was produced: llm_generated, fallback_template, or unsupported.",
    )
    fallback_used: bool = Field(
        default=False,
        description="Whether the deterministic fallback template was used.",
    )
    fallback_reason: str = Field(
        default="",
        description="Reason the fallback template was used, if any.",
    )
    generation_inputs_summary: list[str] = Field(
        default_factory=list,
        description="Inputs included in the app generation prompt.",
    )
    reflection_attempts: int = Field(
        default=0,
        description="Number of Builder repair attempts and downstream patch/reflection attempts.",
    )
    repair_attempted: bool = Field(
        default=False,
        description="Whether the Builder attempted at least one in-agent repair before fallback or success.",
    )
    initial_validation_error_code: str = Field(
        default="",
        description="First Builder validation error code observed before any repair attempt.",
    )
    repair_validation_error_code: str = Field(
        default="",
        description="Last Builder validation error code observed during repair attempts, if any.",
    )
    repair_history: list[str] = Field(
        default_factory=list,
        description="Short per-attempt repair history entries emitted by the Builder.",
    )
    builder_errors: list[str] = Field(
        default_factory=list,
        description="Failure codes observed during Builder generation or fallback.",
    )
