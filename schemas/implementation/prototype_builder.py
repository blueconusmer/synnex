from __future__ import annotations

from typing import Any

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


class AppFlowScreen(SchemaModel):
    screen_id: str = Field(description="Literal screen constant such as SCREEN_START.")
    purpose: str = Field(default="", description="What this screen is responsible for.")
    interaction_type: str = Field(
        default="",
        description="Interaction type handled on this screen, if any.",
    )
    required_ui_elements: list[str] = Field(
        default_factory=list,
        description="UI elements or literals that should appear on this screen.",
    )


class AppFlowTransition(SchemaModel):
    from_screen: str = Field(description="Starting screen constant.")
    to_screen: str = Field(description="Target screen constant.")
    trigger: str = Field(default="", description="Event that triggers the transition.")
    state_assignment: str = Field(
        description="Literal current_screen assignment required in app.py.",
    )


class AppFlowPath(SchemaModel):
    target_screen: str = Field(description="Destination screen constant.")
    trigger: str = Field(default="", description="Condition or trigger for entering this path.")
    state_assignment: str = Field(
        default="",
        description="Literal state assignment that must appear in source.",
    )
    notes: str = Field(default="", description="Short explanation of the path.")


class AppFlowPlanOutput(SchemaModel):
    interaction_mode: str = Field(description="Interaction mode the app flow implements.")
    content_runtime_source: str = Field(
        description="Primary runtime collection such as quests or interaction_units."
    )
    content_loading_order: str = Field(
        default="outputs_first",
        description="How app.py loads content files. Must remain outputs_first.",
    )
    screens: list[AppFlowScreen] = Field(
        default_factory=list,
        description="Screen-level plan for the generated app.",
    )
    transitions: list[AppFlowTransition] = Field(
        default_factory=list,
        description="Explicit current_screen transitions required by the runtime contract.",
    )
    required_functions: list[str] = Field(
        default_factory=list,
        description="Function names that must appear in the generated app.",
    )
    required_runtime_literals: list[str] = Field(
        default_factory=list,
        description="Runtime literals that should appear in generated source.",
    )
    forbidden_runtime_literals: list[str] = Field(
        default_factory=list,
        description="Legacy runtime access literals that must not appear in source.",
    )
    forbidden_raw_runtime_fields: list[str] = Field(
        default_factory=list,
        description="Raw quest field literals that must not appear outside normalization helpers.",
    )
    data_bindings: dict[str, Any] = Field(
        default_factory=dict,
        description="Runtime binding summary, including collection names and field mappings.",
    )
    error_path: AppFlowPath | None = Field(
        default=None,
        description="Error-handling path that should be reachable in the app flow.",
    )
    result_path: AppFlowPath | None = Field(
        default=None,
        description="Primary result/completion path that should be reachable in the app flow.",
    )
    generation_notes: list[str] = Field(
        default_factory=list,
        description="Notes explaining how the plan interprets the service contract.",
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
    generation_stage: str = Field(
        default="direct_code",
        description="Builder generation strategy, for example direct_code or plan_then_code.",
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
    plan_validation_passed: bool = Field(
        default=False,
        description="Whether the intermediate AppFlowPlan passed validation before code generation.",
    )
    plan_repair_attempts: int = Field(
        default=0,
        description="Number of plan repair attempts performed before code generation.",
    )
    plan_summary: list[str] = Field(
        default_factory=list,
        description="Short summary of the validated AppFlowPlan and its contract coverage.",
    )
    app_flow_plan: dict[str, Any] = Field(
        default_factory=dict,
        description="Serialized intermediate AppFlowPlan used for plan-then-code generation.",
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
