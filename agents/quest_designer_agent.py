"""Rule-based Quest Designer Agent implementation.

This module turns planning and question-agent design outputs into reusable
quest structures for the current sequential pipeline stage.
"""

from __future__ import annotations

from schemas.common import SampleQuest
from schemas.quest_designer import QuestDesignerInput, QuestDesignerOutput


def run_quest_designer_agent(agent_input: QuestDesignerInput) -> QuestDesignerOutput:
    """Create the minimum quest design package for the project stage.

    Args:
        agent_input: Structured input containing planner and question-power
            design outputs.

    Returns:
        QuestDesignerOutput: Quest types, flow, samples, and interaction patterns.
    """

    planner_output = agent_input.planner_output
    question_output = agent_input.question_power_output
    target_user = planner_output.target_user

    return QuestDesignerOutput(
        quest_types=[
            "Choose the better question",
            "Find missing parts in a question",
            "Rewrite a vague question",
            "Create a question for a specific learning situation",
        ],
        quest_flow=[
            "Present a weak or incomplete learner question.",
            "Ask the learner to identify what is missing.",
            "Guide the learner to rewrite the question.",
            "Explain why the revised question is stronger.",
        ],
        sample_quests=[
            SampleQuest(
                title="Make the science question more specific",
                objective="Help the learner name the exact topic and difficulty point.",
                learner_prompt=(
                    f"Rewrite this question for {target_user}: 'I do not get science.'"
                ),
                expected_output=(
                    "A revised question that names the science topic and what feels confusing."
                ),
            ),
            SampleQuest(
                title="Add context to a homework help question",
                objective="Help the learner explain the current study situation.",
                learner_prompt="Improve this question: 'Can someone help me with my assignment?'",
                expected_output=(
                    "A revised question that includes the subject, task type, and current obstacle."
                ),
            ),
            SampleQuest(
                title="Clarify the kind of help you want",
                objective="Help the learner state the desired support clearly.",
                learner_prompt="Rewrite this question: 'I am stuck in math.'",
                expected_output=(
                    "A revised question that says whether the learner wants an explanation, "
                    "an example, or feedback on a question."
                ),
            ),
        ],
        interaction_patterns=[
            "Multiple-choice comparison",
            "Checklist-based diagnosis",
            "Short rewrite task",
            "Scenario-based question building",
            f"Principle reflection using: {', '.join(question_output.core_principles)}",
        ],
    )


def build_sample_quest_designer_input() -> QuestDesignerInput:
    """Create a reusable sample input for local testing."""

    from agents.product_planner_agent import (
        build_sample_product_planner_input,
        run_product_planner_agent,
    )
    from agents.question_power_designer_agent import run_question_power_designer_agent
    from schemas.question_power_designer import QuestionPowerDesignerInput

    planner_output = run_product_planner_agent(build_sample_product_planner_input())
    question_output = run_question_power_designer_agent(
        QuestionPowerDesignerInput(planner_output=planner_output)
    )
    return QuestDesignerInput(
        planner_output=planner_output,
        question_power_output=question_output,
    )


if __name__ == "__main__":
    sample_output = run_quest_designer_agent(build_sample_quest_designer_input())
    print(sample_output.model_dump_json(indent=2))
