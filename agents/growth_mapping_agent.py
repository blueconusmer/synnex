"""Rule-based Growth Mapping Agent implementation.

This module maps quest outputs to simple scoring, growth, and feedback rules
for the current team-building stage.
"""

from __future__ import annotations

from schemas.common import FeedbackTemplate, GrowthLevel, ResultMessageRule, ScoringRule
from schemas.growth_mapping import GrowthMappingInput, GrowthMappingOutput


def run_growth_mapping_agent(agent_input: GrowthMappingInput) -> GrowthMappingOutput:
    """Convert quest and question-design outputs into growth mapping rules.

    Args:
        agent_input: Structured input containing question-power and quest outputs.

    Returns:
        GrowthMappingOutput: Scoring rules, growth levels, and feedback rules.
    """

    criteria = _extract_criteria(agent_input.question_power_output.core_principles)
    score_rules = [
        ScoringRule(
            criterion=criterion,
            rule=f"Give 1 point when the learner improves {criterion} in the revised question.",
        )
        for criterion in criteria
    ]

    feedback_templates = [
        FeedbackTemplate(
            condition=f"{criterion} improved",
            message=_feedback_message_for(criterion),
        )
        for criterion in criteria
    ]

    return GrowthMappingOutput(
        scoring_rules=score_rules,
        growth_levels=[
            GrowthLevel(
                level_name="Starter",
                description="Can notice that a question is too vague.",
            ),
            GrowthLevel(
                level_name="Builder",
                description="Can improve at least one missing element in a question.",
            ),
            GrowthLevel(
                level_name="Question Coach",
                description="Can produce a clear question with specificity, context, and purpose.",
            ),
        ],
        feedback_templates=feedback_templates,
        result_message_rules=[
            ResultMessageRule(
                section="summary",
                rule="Start by naming the strongest improvement in the revised question.",
            ),
            ResultMessageRule(
                section="score",
                rule=f"Show a simple score out of {len(score_rules)} based on the core criteria.",
            ),
            ResultMessageRule(
                section="next_step",
                rule="End with one actionable suggestion for the learner's next revision.",
            ),
        ],
    )


def build_sample_growth_mapping_input() -> GrowthMappingInput:
    """Create a reusable sample input for local testing."""

    from agents.product_planner_agent import (
        build_sample_product_planner_input,
        run_product_planner_agent,
    )
    from agents.question_power_designer_agent import run_question_power_designer_agent
    from agents.quest_designer_agent import run_quest_designer_agent
    from schemas.question_power_designer import QuestionPowerDesignerInput
    from schemas.quest_designer import QuestDesignerInput

    planner_output = run_product_planner_agent(build_sample_product_planner_input())
    question_output = run_question_power_designer_agent(
        QuestionPowerDesignerInput(planner_output=planner_output)
    )
    quest_output = run_quest_designer_agent(
        QuestDesignerInput(
            planner_output=planner_output,
            question_power_output=question_output,
        )
    )
    return GrowthMappingInput(
        question_power_output=question_output,
        quest_output=quest_output,
    )


def _extract_criteria(core_principles: list[str]) -> list[str]:
    criteria: list[str] = []

    for principle in core_principles:
        lowered = principle.lower()
        if "specific" in lowered:
            criteria.append("specificity")
        elif "context" in lowered:
            criteria.append("context")
        elif "help" in lowered or "purpose" in lowered:
            criteria.append("purpose")

    return criteria or ["specificity", "context", "purpose"]


def _feedback_message_for(criterion: str) -> str:
    if criterion == "specificity":
        return "Your question got stronger because it now names the exact topic."
    if criterion == "context":
        return "Your question is clearer because it now explains the learning situation."
    return "Your question is more useful because it says what kind of help you want."


if __name__ == "__main__":
    sample_output = run_growth_mapping_agent(build_sample_growth_mapping_input())
    print(sample_output.model_dump_json(indent=2))
