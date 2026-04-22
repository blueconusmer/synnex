from __future__ import annotations

from agents.base import Agent, Payload


class QuestionPowerDesignerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Question Power Designer Agent",
            slug="question_power_designer",
            description="Design the question-improvement agent principles and prompt shape.",
        )

    def run(self, context: Payload) -> Payload:
        planner_output = context["stage_outputs"]["product_planner"]["artifacts"]

        return {
            "agent": self.name,
            "slug": self.slug,
            "source_of_truth": "docs/project_context.md",
            "artifacts": {
                "agent_role_definition": (
                    "A question tutor that helps students make their questions more specific, "
                    "contextual, and purpose-driven."
                ),
                "question_improvement_principles": [
                    "Increase specificity.",
                    "Make the missing context visible.",
                    "Clarify the kind of help the student wants.",
                ],
                "prohibited_behaviors": [
                    "Do not answer every vague question directly without improving it first.",
                    "Do not optimize for broad knowledge delivery over question improvement.",
                    "Do not behave like a production-ready tutoring system yet.",
                ],
                "prompt_outline": {
                    "system_goal": "Guide the user to improve the quality of the question.",
                    "target_user": planner_output["target_user"],
                    "tone": "Supportive, structured, and concise.",
                    "checklist": ["specificity", "context", "purpose"],
                },
                "few_shot_outline": [
                    "Rewrite a vague study question into a clearer one.",
                    "Identify missing context in a homework-related question.",
                    "Show how to express the desired kind of help.",
                ],
            },
            "handoff": {
                "next_agent": "Quest Designer Agent",
                "focus": [
                    "Design interaction patterns that reinforce specificity, context, and purpose.",
                    "Use structured quest formats instead of open-ended product flows.",
                ],
            },
        }
