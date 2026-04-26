from __future__ import annotations

from pydantic import Field

from schemas.implementation.common import AgentLabel, QuizItem, SchemaModel
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput


class ContentInteractionInput(SchemaModel):
    spec_intake_output: SpecIntakeOutput = Field(
        description="Normalized service spec from the intake stage."
    )
    requirement_mapping_output: RequirementMappingOutput = Field(
        description="Implementation contract from the requirement mapping stage."
    )


class ContentInteractionOutput(SchemaModel):
    agent: AgentLabel | None = Field(default=None, description="Agent label metadata.")
    service_summary: str = Field(
        description="Short summary describing the generated quiz service."
    )
    quiz_types: list[str] = Field(
        default_factory=list,
        description="Distinct quiz types represented in the generated content.",
    )
    items: list[QuizItem] = Field(
        default_factory=list,
        description="Generated quiz items for the current MVP.",
    )
    answer_key: dict[str, str] = Field(
        default_factory=dict,
        description="Answer key keyed by item id.",
    )
    explanations: dict[str, str] = Field(
        default_factory=dict,
        description="Explanation text keyed by item id.",
    )
    learning_points: dict[str, str] = Field(
        default_factory=dict,
        description="Learning point text keyed by item id.",
    )
    interaction_notes: list[str] = Field(
        default_factory=list,
        description="Notes describing how the learner should experience the quiz flow.",
    )
