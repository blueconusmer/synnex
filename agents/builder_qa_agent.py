"""Rule-based Builder & QA Agent implementation.

This module integrates upstream artifacts into implementation notes and QA
guidance for the minimum sequential pipeline stage.
"""

from __future__ import annotations

from schemas.builder_qa import BuilderQAInput, BuilderQAOutput
from schemas.common import ImplementationStep, IntegrationNote, QAIssue


def run_builder_qa_agent(agent_input: BuilderQAInput) -> BuilderQAOutput:
    """Create implementation and QA artifacts from prior agent outputs.

    Args:
        agent_input: Structured input containing all upstream agent outputs.

    Returns:
        BuilderQAOutput: Integration-oriented implementation and QA summary.
    """

    planner_output = agent_input.planner_output
    question_output = agent_input.question_power_output
    quest_output = agent_input.quest_output
    growth_output = agent_input.growth_mapping_output

    return BuilderQAOutput(
        implementation_plan=[
            ImplementationStep(
                step_name="Wire schema-based agent functions",
                description=(
                    "Call each agent in sequence and pass validated output models to the next agent."
                ),
            ),
            ImplementationStep(
                step_name="Persist stage outputs as JSON",
                description="Save each agent output with predictable file names for later review.",
            ),
            ImplementationStep(
                step_name="Generate a human-readable final summary",
                description="Combine the main outputs into a markdown summary for quick inspection.",
            ),
        ],
        integration_notes=[
            IntegrationNote(
                from_agent="Product Planner Agent",
                to_agent="Question Power Designer Agent",
                note=(
                    "Use project_goal, target_user, and user_flow to shape the question-power role."
                ),
            ),
            IntegrationNote(
                from_agent="Question Power Designer Agent",
                to_agent="Quest Designer Agent",
                note=(
                    "Use core_principles and prompt_draft to design quests that reinforce "
                    "specificity, context, and purpose."
                ),
            ),
            IntegrationNote(
                from_agent="Quest Designer Agent",
                to_agent="Growth Mapping Agent",
                note=(
                    f"Map {len(quest_output.quest_types)} quest types and learner actions to "
                    "scoring and feedback rules."
                ),
            ),
            IntegrationNote(
                from_agent="Growth Mapping Agent",
                to_agent="Builder & QA Agent",
                note=(
                    f"Integrate {len(growth_output.scoring_rules)} scoring rules into the final "
                    "implementation and QA plan."
                ),
            ),
        ],
        qa_checklist=[
            "Does each agent accept a schema-based input and return a schema-based output?",
            "Can the pipeline run sequentially without external LLM services?",
            "Are JSON outputs readable and ready for downstream use?",
            "Do the outputs stay aligned with docs/project_context.md?",
        ],
        qa_issues=[
            QAIssue(
                issue="Prompt drafts are still rule-based placeholders.",
                impact="Later stages may need richer prompt wording before real model integration.",
                mitigation="Refine prompt_draft and few_shot_examples before adding LLM calls.",
            ),
            QAIssue(
                issue="Quest and growth rules are deterministic templates.",
                impact="The pipeline validates structure more than content quality.",
                mitigation="Add content review and optional validation checks in the next stage.",
            ),
        ],
        final_summary_points=[
            f"The project goal is focused on: {planner_output.project_goal}",
            f"The question-power agent is grounded in {len(question_output.core_principles)} core principles.",
            f"The current design includes {len(quest_output.sample_quests)} sample quests and "
            f"{len(growth_output.scoring_rules)} scoring rules.",
        ],
    )


def build_sample_builder_qa_input() -> BuilderQAInput:
    """Create a reusable sample input for local testing."""

    from agents.product_planner_agent import (
        build_sample_product_planner_input,
        run_product_planner_agent,
    )
    from agents.question_power_designer_agent import run_question_power_designer_agent
    from agents.quest_designer_agent import run_quest_designer_agent
    from agents.growth_mapping_agent import run_growth_mapping_agent
    from schemas.growth_mapping import GrowthMappingInput
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
    growth_output = run_growth_mapping_agent(
        GrowthMappingInput(
            question_power_output=question_output,
            quest_output=quest_output,
        )
    )
    return BuilderQAInput(
        planner_output=planner_output,
        question_power_output=question_output,
        quest_output=quest_output,
        growth_mapping_output=growth_output,
    )


if __name__ == "__main__":
    sample_output = run_builder_qa_agent(build_sample_builder_qa_input())
    print(sample_output.model_dump_json(indent=2))
