"""Rule-based Product Planner Agent implementation.

This module provides a callable unit for the current team-building stage.
It consumes the Product Planner input schema and returns a structured
Product Planner output without relying on external LLM APIs.
"""

from __future__ import annotations

from schemas.common import ProjectBrief
from schemas.product_planner import ProductPlannerInput, ProductPlannerOutput


def run_product_planner_agent(agent_input: ProductPlannerInput) -> ProductPlannerOutput:
    """Build the minimum planning artifact for the current project stage.

    Args:
        agent_input: Structured input containing the project brief.

    Returns:
        ProductPlannerOutput: Planning output that downstream agents can reuse.
    """

    brief = agent_input.project_brief
    mvp_scope = [
        "Define the five-agent collaboration structure.",
        "Prepare structured input and output contracts for each agent.",
        "Validate one sequential end-to-end execution flow.",
    ]

    if _has_7_day_constraint(brief.constraints):
        mvp_scope.append("Keep the scope small enough to validate within a 7-day sprint.")

    if _has_before_after_constraint(brief.constraints):
        mvp_scope.append("Emphasize a before/after question-improvement experience.")

    return ProductPlannerOutput(
        problem_definition=(
            f"The target user is {brief.target_user}, and the team first needs a minimum AI "
            "workflow that can produce planning and design artifacts for the Question-Power "
            "Co-Learner before building the full service."
        ),
        project_goal=brief.project_goal,
        target_user=brief.target_user,
        mvp_scope=mvp_scope,
        excluded_scope=[
            "Production-ready chatbot implementation",
            "External LLM API integration",
            "Database and authentication",
            "High-fidelity UI",
        ],
        user_flow=[
            "Clarify the project purpose and current stage.",
            "Define how the question-improvement agent should behave.",
            "Design structured quest interactions for learners.",
            "Connect quest outcomes to growth and feedback rules.",
            "Integrate outputs into implementation notes and QA checks.",
        ],
    )


def build_sample_product_planner_input() -> ProductPlannerInput:
    """Create a reusable sample input for local testing."""

    return ProductPlannerInput(
        project_brief=ProjectBrief(
            project_name="Synnex Question-Power Co-Learner",
            project_goal="Design the minimum AI agent team for a question-improvement co-learner.",
            target_user="Middle school students who need help improving vague questions.",
            constraints=[
                "Timeline: 7 days",
                "Core experience: show before/after question improvement",
                "Do not use external LLM APIs in this stage",
            ],
        )
    )


def _has_7_day_constraint(constraints: list[str]) -> bool:
    return any("7" in constraint for constraint in constraints)


def _has_before_after_constraint(constraints: list[str]) -> bool:
    return any("before/after" in constraint.lower() for constraint in constraints)


if __name__ == "__main__":
    sample_output = run_product_planner_agent(build_sample_product_planner_input())
    print(sample_output.model_dump_json(indent=2))
