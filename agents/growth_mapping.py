from __future__ import annotations

from agents.base import Agent, Payload


class GrowthMappingAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Growth Mapping Agent",
            slug="growth_mapping",
            description="Connect quest outcomes to growth rules and feedback templates.",
        )

    def run(self, context: Payload) -> Payload:
        quest_output = context["stage_outputs"]["quest_designer"]["artifacts"]

        return {
            "agent": self.name,
            "slug": self.slug,
            "source_of_truth": "docs/project_context.md",
            "artifacts": {
                "score_rules": [
                    "Add 1 point when the learner improves specificity.",
                    "Add 1 point when the learner adds relevant context.",
                    "Add 1 point when the learner clearly states the desired help.",
                ],
                "growth_stages": [
                    "Starter: can notice weak questions",
                    "Builder: can improve one missing element",
                    "Coach-ready: can produce a clear question with all three elements",
                ],
                "feedback_templates": [
                    "Your question became clearer because it now shows the exact topic.",
                    "Your question improved because it explains the learning situation.",
                    "Your question is stronger because it states the kind of help you want.",
                ],
                "result_message_structure": {
                    "summary": "What improved in the learner's question",
                    "score": "Simple three-point rubric",
                    "next_step": "One suggestion for the next revision",
                },
                "quest_alignment": quest_output["quest_types"],
            },
            "handoff": {
                "next_agent": "Builder & QA Agent",
                "focus": [
                    "Integrate the planning, prompt, quest, and growth outputs.",
                    "Turn them into implementation notes and QA checkpoints.",
                ],
            },
        }
