from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import AgentLabel, QuizGenerationRequirements, SchemaModel
from schemas.implementation.orchestration_decision import RetryInstruction
from schemas.implementation.spec_intake import SpecIntakeOutput


class FilePlan(SchemaModel):
    path: str = Field(description="Relative file path to create or update.")
    purpose: str = Field(description="Why the file exists in the implementation flow.")
    producing_agent: str = Field(description="Agent responsible for the file.")


class RequirementMappingInput(SchemaModel):
    spec_intake_output: SpecIntakeOutput = Field(
        description="Structured output from the spec intake stage."
    )
    retry_instruction: RetryInstruction | None = Field(
        default=None,
        description="Optional feedback-loop retry instruction for revising requirement mapping.",
    )


class RequirementMappingOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    implementation_targets: list[str] = Field(
        default_factory=list,
        description="High-level implementation targets for the current service.",
    )
    file_plan: list[FilePlan] = Field(
        default_factory=list,
        description="Planned files for the implementation pipeline.",
    )
    quiz_generation_requirements: QuizGenerationRequirements = Field(
        description="Quiz generation contract for the content agent."
    )
    app_constraints: list[str] = Field(
        default_factory=list,
        description="Constraints the MVP app must satisfy.",
    )
    test_strategy: list[str] = Field(
        default_factory=list,
        description="Checks the run-test-fix stage should execute.",
    )
