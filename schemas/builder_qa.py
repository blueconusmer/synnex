from __future__ import annotations

from pydantic import Field

from schemas.common import ImplementationStep, IntegrationNote, QAIssue, SchemaModel
from schemas.growth_mapping import GrowthMappingOutput
from schemas.product_planner import ProductPlannerOutput
from schemas.question_power_designer import QuestionPowerDesignerOutput
from schemas.quest_designer import QuestDesignerOutput


class BuilderQAInput(SchemaModel):
    planner_output: ProductPlannerOutput = Field(
        description="Planning output that defines the stage goal and scope."
    )
    question_power_output: QuestionPowerDesignerOutput = Field(
        description="Question-power design output for prompt and role alignment."
    )
    quest_output: QuestDesignerOutput = Field(
        description="Quest design output for learner interaction planning."
    )
    growth_mapping_output: GrowthMappingOutput = Field(
        description="Growth mapping output for feedback and scoring integration."
    )


class BuilderQAOutput(SchemaModel):
    implementation_plan: list[ImplementationStep] = Field(
        default_factory=list,
        description="Implementation steps for the next coding phase.",
    )
    integration_notes: list[IntegrationNote] = Field(
        default_factory=list,
        description="Notes describing how outputs connect across agents.",
    )
    qa_checklist: list[str] = Field(
        default_factory=list,
        description="Checklist for verifying the current team-building skeleton.",
    )
    qa_issues: list[QAIssue] = Field(
        default_factory=list,
        description="Known issues or risks to verify in future work.",
    )
    final_summary_points: list[str] = Field(
        default_factory=list,
        description="Concise summary points for the current stage output.",
    )
