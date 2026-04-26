from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import AgentLabel, SchemaModel
from schemas.implementation.implementation_spec import ImplementationSpec


class SpecIntakeInput(SchemaModel):
    implementation_spec: ImplementationSpec = Field(
        description="Parsed implementation specification from the source Markdown file."
    )


class SpecIntakeOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    team_identity: str = Field(description="Implementation team identity.")
    service_summary: str = Field(description="One-paragraph summary of the requested service.")
    normalized_requirements: list[str] = Field(
        default_factory=list,
        description="Normalized requirements extracted from the spec.",
    )
    delivery_expectations: list[str] = Field(
        default_factory=list,
        description="Expected deliverables for downstream agents.",
    )
    acceptance_focus: list[str] = Field(
        default_factory=list,
        description="Key acceptance points for downstream validation.",
    )
