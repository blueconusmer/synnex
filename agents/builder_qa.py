from __future__ import annotations

from agents.base import Agent, Payload


class BuilderQAAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            name="Builder & QA Agent",
            slug="builder_qa",
            description="Integrate upstream outputs into implementation notes and QA guidance.",
        )

    def run(self, context: Payload) -> Payload:
        planner_output = context["stage_outputs"]["product_planner"]["artifacts"]
        question_output = context["stage_outputs"]["question_power_designer"]["artifacts"]
        quest_output = context["stage_outputs"]["quest_designer"]["artifacts"]
        growth_output = context["stage_outputs"]["growth_mapping"]["artifacts"]

        return {
            "agent": self.name,
            "slug": self.slug,
            "source_of_truth": "docs/project_context.md",
            "artifacts": {
                "implementation_plan": [
                    "Keep the repository centered on team-building artifacts.",
                    "Represent each agent with a structured output contract.",
                    "Run agents sequentially and persist outputs as JSON.",
                    "Leave external LLM integration out of the current stage.",
                ],
                "integration_notes": {
                    "planner_to_designer": planner_output["project_goal"],
                    "designer_to_quest": question_output["question_improvement_principles"],
                    "quest_to_growth": quest_output["quest_types"],
                    "growth_to_build": growth_output["result_message_structure"],
                },
                "qa_checklist": [
                    "Does each agent have a clear role and output?",
                    "Can the pipeline run end-to-end without external services?",
                    "Are outputs structured and easy for the next agent to consume?",
                    "Does the repository reflect the current stage rather than a full product build?",
                ],
                "risks_and_issues": [
                    "Outputs may stay too abstract without real prompt iteration.",
                    "Schema drift can appear if later files change independently of the source document.",
                    "The demo pipeline validates structure, not model quality.",
                ],
                "final_summary_points": [
                    "The repository now expresses the five-agent team skeleton.",
                    "The current implementation prioritizes structure over full functionality.",
                    "The next phase can deepen prompts, schemas, and validation rules.",
                ],
            },
            "handoff": {
                "next_agent": None,
                "focus": [
                    "Use the generated artifacts as the base for future prompt and schema refinement."
                ],
            },
        }
