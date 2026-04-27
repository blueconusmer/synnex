from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import AgentLabel, SchemaModel
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.implementation_spec import ImplementationSpec
from schemas.implementation.prototype_builder import PrototypeBuilderOutput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.run_test_and_fix import RunTestAndFixOutput
from schemas.implementation.spec_intake import SpecIntakeOutput


class QAAlignmentInput(SchemaModel):
    spec_intake_output: SpecIntakeOutput = Field(
        description="Normalized intake output."
    )
    requirement_mapping_output: RequirementMappingOutput = Field(
        description="Implementation contract output."
    )
    content_interaction_output: ContentInteractionOutput = Field(
        description="Generated quiz contents and interaction notes."
    )
    prototype_builder_output: PrototypeBuilderOutput = Field(
        description="Generated code artifacts."
    )
    run_test_and_fix_output: RunTestAndFixOutput = Field(
        description="Execution, test, and fix results."
    )
    implementation_spec: ImplementationSpec | None = Field(
        default=None,
        description="Runtime implementation configuration passed through the pipeline.",
    )


class QAAlignmentOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    alignment_status: str = Field(description="Overall alignment status.")
    qa_checklist: list[str] = Field(
        default_factory=list,
        description="Checklist for the final QA review.",
    )
    qa_issues: list[str] = Field(
        default_factory=list,
        description="Issues discovered during QA.",
    )
    change_log_entries: list[str] = Field(
        default_factory=list,
        description="Entries that should be written to the change log.",
    )
    final_summary_points: list[str] = Field(
        default_factory=list,
        description="Summary points for the final implementation report.",
    )
