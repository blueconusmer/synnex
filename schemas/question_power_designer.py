from __future__ import annotations

from pydantic import Field

from schemas.common import FewShotExample, PromptDraft, SchemaModel
from schemas.product_planner import ProductPlannerOutput


class QuestionPowerDesignerInput(SchemaModel):
    planner_output: ProductPlannerOutput = Field(
        description="Structured planning output from the Product Planner Agent."
    )


class QuestionPowerDesignerOutput(SchemaModel):
    agent_role: str = Field(description="Role definition for the question-power agent.")
    core_principles: list[str] = Field(
        default_factory=list,
        description="Core design principles for improving question quality.",
    )
    forbidden_actions: list[str] = Field(
        default_factory=list,
        description="Actions the question-power agent should avoid.",
    )
    prompt_draft: PromptDraft = Field(
        description="Draft prompt structure for later implementation."
    )
    few_shot_examples: list[FewShotExample] = Field(
        default_factory=list,
        description="Few-shot examples showing desired agent behavior.",
    )
