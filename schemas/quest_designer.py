from __future__ import annotations

from pydantic import Field

from schemas.common import SampleQuest, SchemaModel
from schemas.product_planner import ProductPlannerOutput
from schemas.question_power_designer import QuestionPowerDesignerOutput


class QuestDesignerInput(SchemaModel):
    planner_output: ProductPlannerOutput = Field(
        description="Planning output used to keep quests aligned with project scope."
    )
    question_power_output: QuestionPowerDesignerOutput = Field(
        description="Question-power design output used to align quests with core principles."
    )


class QuestDesignerOutput(SchemaModel):
    quest_types: list[str] = Field(
        default_factory=list,
        description="Types of quests the learner can perform.",
    )
    quest_flow: list[str] = Field(
        default_factory=list,
        description="Ordered flow of a quest experience.",
    )
    sample_quests: list[SampleQuest] = Field(
        default_factory=list,
        description="Concrete quest examples for later implementation.",
    )
    interaction_patterns: list[str] = Field(
        default_factory=list,
        description="Interaction patterns the quest system can reuse.",
    )
