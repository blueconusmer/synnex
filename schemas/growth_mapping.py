from __future__ import annotations

from pydantic import Field

from schemas.common import FeedbackTemplate, GrowthLevel, ResultMessageRule, SchemaModel, ScoringRule
from schemas.question_power_designer import QuestionPowerDesignerOutput
from schemas.quest_designer import QuestDesignerOutput


class GrowthMappingInput(SchemaModel):
    question_power_output: QuestionPowerDesignerOutput = Field(
        description="Question-power design output used to keep scoring aligned with principles."
    )
    quest_output: QuestDesignerOutput = Field(
        description="Quest design output used to map activities to growth feedback."
    )


class GrowthMappingOutput(SchemaModel):
    scoring_rules: list[ScoringRule] = Field(
        default_factory=list,
        description="Simple scoring rules for question-improvement outcomes.",
    )
    growth_levels: list[GrowthLevel] = Field(
        default_factory=list,
        description="Growth levels for learner progress.",
    )
    feedback_templates: list[FeedbackTemplate] = Field(
        default_factory=list,
        description="Templates for learner-facing feedback.",
    )
    result_message_rules: list[ResultMessageRule] = Field(
        default_factory=list,
        description="Rules for composing result messages after quests.",
    )
