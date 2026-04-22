"""Rule-based Question Power Designer Agent implementation.

This module converts structured planning output into a minimum
question-improvement agent design without calling external model APIs.
"""

from __future__ import annotations

from schemas.common import FewShotExample, PromptDraft
from schemas.question_power_designer import (
    QuestionPowerDesignerInput,
    QuestionPowerDesignerOutput,
)


def run_question_power_designer_agent(
    agent_input: QuestionPowerDesignerInput,
) -> QuestionPowerDesignerOutput:
    """Build the question-power agent definition from planner output.

    Args:
        agent_input: Structured input containing planner output.

    Returns:
        QuestionPowerDesignerOutput: Prompt and behavior definition for the
        question-improvement agent.
    """

    planner_output = agent_input.planner_output
    target_user = planner_output.target_user

    return QuestionPowerDesignerOutput(
        agent_role=(
            f"Act as a question tutor for {target_user} and help learners improve "
            "their questions before moving to direct answers."
        ),
        core_principles=[
            "Increase specificity in every learner question.",
            "Expose the learning context behind the question.",
            "Clarify what kind of help the learner wants.",
        ],
        forbidden_actions=[
            "Do not answer vague questions without improving them first.",
            "Do not behave like a general knowledge chatbot.",
            "Do not expand into full product behavior during the team-building stage.",
        ],
        prompt_draft=PromptDraft(
            system_role=f"You are a question tutor for {target_user}.",
            instruction_steps=[
                "Identify what is missing from the current question.",
                "Guide the learner to rewrite the question with more clarity.",
                "Explain the revision using specificity, context, and purpose.",
            ],
            response_style="Supportive, concise, and structured.",
            output_format=[
                "missing_elements",
                "revised_question",
                "improvement_explanation",
            ],
        ),
        few_shot_examples=[
            FewShotExample(
                situation="The learner asks for broad homework help.",
                user_question="Can you help me with math homework?",
                assistant_guidance=(
                    "Ask which math unit the learner is studying and what part feels hard, "
                    "then help rewrite the question with that detail."
                ),
                improvement_focus=["specificity", "context"],
            ),
            FewShotExample(
                situation="The learner does not say what kind of help is needed.",
                user_question="I do not understand science.",
                assistant_guidance=(
                    "Ask whether the learner wants an explanation, an example, or help "
                    "rewriting the question."
                ),
                improvement_focus=["purpose"],
            ),
        ],
    )


def build_sample_question_power_designer_input() -> QuestionPowerDesignerInput:
    """Create a reusable sample input for local testing."""

    from agents.product_planner_agent import (
        build_sample_product_planner_input,
        run_product_planner_agent,
    )

    planner_output = run_product_planner_agent(build_sample_product_planner_input())
    return QuestionPowerDesignerInput(planner_output=planner_output)


if __name__ == "__main__":
    sample_output = run_question_power_designer_agent(
        build_sample_question_power_designer_input()
    )
    print(sample_output.model_dump_json(indent=2))
