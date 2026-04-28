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
