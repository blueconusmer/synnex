from __future__ import annotations

from agents.base import Agent, Payload


class QuestDesignerAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Quest Designer Agent",
            slug="quest_designer",
            description="Design quest patterns and interaction flows for question improvement.",
        )

    def run(self, context: Payload) -> Payload:
        question_power_output = context["stage_outputs"]["question_power_designer"]["artifacts"]

        return {
            "agent": self.name,
            "slug": self.slug,
            "source_of_truth": "docs/project_context.md",
            "artifacts": {
                "quest_types": [
                    "Choose the better question",
                    "Find missing elements in a question",
                    "Rewrite a vague question",
                    "Create a question for a specific situation",
                ],
                "quest_flow": [
                    "Show the learner a weak or incomplete question.",
                    "Ask the learner to identify what is missing.",
                    "Guide the learner to revise the question.",
                    "Explain the improvement using the question-power checklist.",
                ],
                "interaction_patterns": [
                    "Multiple-choice comparison",
                    "Checklist-based critique",
                    "Short rewrite task",
                    "Scenario-based question creation",
                ],
                "sample_quests": [
                    {
                        "title": "Make the science question more specific",
                        "focus": "specificity",
                    },
                    {
                        "title": "Add context to a homework help question",
                        "focus": "context",
                    },
                    {
                        "title": "State the kind of help you want",
                        "focus": "purpose",
                    },
                ],
                "design_reference": question_power_output["question_improvement_principles"],
            },
            "handoff": {
                "next_agent": "Growth Mapping Agent",
                "focus": [
                    "Map quest performance to feedback and growth stages.",
                    "Keep scoring simple enough for the current team-building stage.",
                ],
            },
        }
