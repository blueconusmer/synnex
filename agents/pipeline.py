from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agents.base import Payload
from agents.builder_qa import BuilderQAAgent
from agents.growth_mapping import GrowthMappingAgent
from agents.planner import ProductPlannerAgent
from agents.question_power import QuestionPowerDesignerAgent
from agents.quest_designer import QuestDesignerAgent


class AgentPipeline:
    def __init__(self) -> None:
        self.agents = [
            ProductPlannerAgent(),
            QuestionPowerDesignerAgent(),
            QuestDesignerAgent(),
            GrowthMappingAgent(),
            BuilderQAAgent(),
        ]

    def run(self, payload: Payload, output_dir: Path) -> Payload:
        context: Payload = {
            "project_brief": payload,
            "stage_outputs": {},
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files: list[str] = []

        for index, agent in enumerate(self.agents, start=1):
            agent_output = agent.run(context)
            context["stage_outputs"][agent.slug] = agent_output

            output_path = output_dir / f"{index:02d}_{agent.slug}.json"
            self._write_json(output_path, agent_output)
            generated_files.append(str(output_path))

        final_summary = {
            "source_of_truth": "docs/project_context.md",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_name": payload.get("project_name", "Synnex Question-Power Co-Learner"),
            "current_stage": "1-stage AI team building",
            "agent_order": [agent.name for agent in self.agents],
            "generated_files": generated_files,
            "next_recommended_step": (
                "Refine prompts, schemas, and validation rules before introducing any LLM integration."
            ),
        }

        final_summary_path = output_dir / "99_final_summary.json"
        self._write_json(final_summary_path, final_summary)

        return {
            "output_dir": str(output_dir),
            "generated_files": generated_files,
            "final_summary_path": str(final_summary_path),
        }

    @staticmethod
    def _write_json(path: Path, payload: Payload) -> None:
        with path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
