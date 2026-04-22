from __future__ import annotations

from agents.base import Agent, Payload


class ProductPlannerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Product Planner Agent",
            slug="product_planner",
            description="Define the project goal, scope, target user, and baseline user flow.",
        )

    def run(self, context: Payload) -> Payload:
        brief = context["project_brief"]
        target_user = brief.get(
            "target_user",
            "Middle school students who need help making their questions clearer.",
        )
        constraints = brief.get("constraints", [])

        return {
            "agent": self.name,
            "slug": self.slug,
            "source_of_truth": "docs/project_context.md",
            "project_stage": "1-stage AI team building",
            "artifacts": {
                "problem_definition": (
                    "Build the minimum AI team structure that can produce service-planning "
                    "artifacts for a Question-Power Co-Learner."
                ),
                "project_goal": brief.get(
                    "project_goal",
                    brief.get(
                        "current_goal",
                    "Verify a minimum end-to-end AI agent workflow."
                    ),
                ),
                "target_user": target_user,
                "mvp_scope": [
                    "Define the five-agent collaboration structure.",
                    "Prepare structured outputs for each agent.",
                    "Support one sequential end-to-end pipeline run.",
                ],
                "excluded_scope": [
                    "Production chatbot implementation",
                    "External LLM API integration",
                    "Database and authentication",
                    "High-fidelity UI",
                ],
                "baseline_user_flow": [
                    "Clarify the project purpose and stage.",
                    "Design the question-improvement agent behavior.",
                    "Design quest interactions for users.",
                    "Connect quest results to growth feedback.",
                    "Integrate outputs into implementation and QA notes.",
                ],
                "constraints": constraints,
            },
            "handoff": {
                "next_agent": "Question Power Designer Agent",
                "focus": [
                    "Use the project goal and target user as the prompt design baseline.",
                    "Keep the work at team-building level rather than full product implementation.",
                ],
            },
        }
