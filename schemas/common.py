from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ProjectBrief(SchemaModel):
    project_name: str = Field(description="Name of the current project.")
    project_goal: str = Field(description="Current stage goal for the project.")
    current_stage: str = Field(
        default="1-stage AI team building",
        description="Current project stage defined by the source-of-truth document.",
    )
    source_of_truth: str = Field(
        default="docs/project_context.md",
        description="Single source of truth for project direction.",
    )
    target_user: str = Field(description="Primary target user for the service concept.")
    constraints: list[str] = Field(
        default_factory=list,
        description="Current implementation constraints for the stage.",
    )


class PromptDraft(SchemaModel):
    system_role: str = Field(description="Core role statement for the question-power agent.")
    instruction_steps: list[str] = Field(
        default_factory=list,
        description="Ordered instructions the agent should follow.",
    )
    response_style: str = Field(description="Desired response tone and style.")
    output_format: list[str] = Field(
        default_factory=list,
        description="Expected structured response components.",
    )


class FewShotExample(SchemaModel):
    situation: str = Field(description="Learning situation for the example.")
    user_question: str = Field(description="Original user question.")
    assistant_guidance: str = Field(description="How the agent should respond.")
    improvement_focus: list[str] = Field(
        default_factory=list,
        description="Question-improvement focus areas highlighted by the example.",
    )


class SampleQuest(SchemaModel):
    title: str = Field(description="Quest title.")
    objective: str = Field(description="Learning objective for the quest.")
    learner_prompt: str = Field(description="Prompt shown to the learner.")
    expected_output: str = Field(description="Expected learner response or improvement.")


class ScoringRule(SchemaModel):
    criterion: str = Field(description="Question-improvement criterion being scored.")
    rule: str = Field(description="Scoring rule for the criterion.")


class GrowthLevel(SchemaModel):
    level_name: str = Field(description="Name of the growth level.")
    description: str = Field(description="What the level means.")


class FeedbackTemplate(SchemaModel):
    condition: str = Field(description="Condition that triggers the feedback.")
    message: str = Field(description="Feedback message template.")


class ResultMessageRule(SchemaModel):
    section: str = Field(description="Message section name.")
    rule: str = Field(description="Rule for composing that section.")


class ImplementationStep(SchemaModel):
    step_name: str = Field(description="Implementation step name.")
    description: str = Field(description="What should be implemented in this step.")


class IntegrationNote(SchemaModel):
    from_agent: str = Field(description="Upstream agent producing the output.")
    to_agent: str = Field(description="Downstream agent consuming the output.")
    note: str = Field(description="Integration note for the handoff.")


class QAIssue(SchemaModel):
    issue: str = Field(description="Known issue or risk to check.")
    impact: str = Field(description="Why the issue matters.")
    mitigation: str = Field(description="How to reduce or check the risk.")
