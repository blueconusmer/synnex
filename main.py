from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, TypeVar

from agents.builder_qa_agent import run_builder_qa_agent
from agents.growth_mapping_agent import run_growth_mapping_agent
from agents.product_planner_agent import run_product_planner_agent
from agents.question_power_designer_agent import run_question_power_designer_agent
from agents.quest_designer_agent import run_quest_designer_agent
from schemas.builder_qa import BuilderQAInput, BuilderQAOutput
from schemas.common import ProjectBrief, SchemaModel
from schemas.growth_mapping import GrowthMappingInput, GrowthMappingOutput
from schemas.product_planner import ProductPlannerInput, ProductPlannerOutput
from schemas.question_power_designer import (
    QuestionPowerDesignerInput,
    QuestionPowerDesignerOutput,
)
from schemas.quest_designer import QuestDesignerInput, QuestDesignerOutput

ModelT = TypeVar("ModelT", bound=SchemaModel)


def build_sample_project_brief() -> ProjectBrief:
    """Create the project brief for the minimum end-to-end pipeline run."""

    return ProjectBrief(
        project_name="시넥스 질문력 Co-Learner",
        project_goal="질문력 Co-Learner 제작용 AI 팀 설계",
        target_user="중학생 질문 개선 챗봇 사용자",
        constraints=[
            "기간: 7일",
            "핵심 경험: 질문 Before/After 개선",
            "현재 단계는 완성형 서비스가 아니라 AI Agent 팀 최소 파이프라인 검증",
            "실제 외부 LLM API는 연결하지 않는다",
        ],
    )


def run_stage(stage_name: str, output_path: Path, runner: Callable[[], ModelT]) -> ModelT:
    """Run a stage, log progress, and persist failures clearly."""

    print(f"[RUNNING] {stage_name}", flush=True)
    try:
        result = runner()
        save_json(output_path, result)
        print(f"[SUCCESS] {stage_name}", flush=True)
        print(f"[OUTPUT] {output_path}", flush=True)
        return result
    except Exception as exc:  # pragma: no cover - defensive runtime logging
        print(f"[FAILED] {stage_name}: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise


def save_json(path: Path, model: SchemaModel) -> None:
    """Write a Pydantic model to a JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(model.model_dump(mode="json"), file, ensure_ascii=False, indent=2)


def write_final_summary(
    path: Path,
    brief: ProjectBrief,
    planner_output: ProductPlannerOutput,
    question_output: QuestionPowerDesignerOutput,
    quest_output: QuestDesignerOutput,
    growth_output: GrowthMappingOutput,
    builder_output: BuilderQAOutput,
) -> None:
    """Create a human-readable markdown summary for the pipeline run."""

    lines = [
        "# Final Summary",
        "",
        "## 전체 프로젝트 목표 요약",
        f"- 프로젝트명: {brief.project_name}",
        f"- 현재 목표: {brief.project_goal}",
        f"- 대상: {brief.target_user}",
        "- 기간: 7일",
        "- 핵심 경험: 질문 Before / After 개선",
        "",
        "## Agent별 핵심 산출물 요약",
        "### Product Planner Agent",
        f"- 문제 정의: {planner_output.problem_definition}",
        f"- MVP 범위: {', '.join(planner_output.mvp_scope)}",
        "",
        "### Question Power Designer Agent",
        f"- Agent 역할: {question_output.agent_role}",
        f"- 핵심 원칙: {', '.join(question_output.core_principles)}",
        "",
        "### Quest Designer Agent",
        f"- 퀘스트 유형 수: {len(quest_output.quest_types)}",
        f"- 대표 퀘스트: {quest_output.sample_quests[0].title}",
        "",
        "### Growth Mapping Agent",
        f"- 점수 규칙 수: {len(growth_output.scoring_rules)}",
        f"- 성장 단계 수: {len(growth_output.growth_levels)}",
        "",
        "### Builder & QA Agent",
        f"- 구현 계획 수: {len(builder_output.implementation_plan)}",
        f"- QA 체크리스트 수: {len(builder_output.qa_checklist)}",
        "",
        "## 최종적으로 생성된 서비스 관련 산출물 요약",
        "- 질문력 Agent 역할 정의",
        f"- 질문 개선 핵심 원칙 {len(question_output.core_principles)}개",
        f"- 퀘스트 설계안 {len(quest_output.sample_quests)}개",
        f"- 성장/피드백 규칙 {len(growth_output.feedback_templates)}개",
        f"- 구현 및 QA 요약 포인트 {len(builder_output.final_summary_points)}개",
        "",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    output_dir = Path("outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    brief = build_sample_project_brief()
    print("[INFO] Starting minimum sequential AI agent pipeline", flush=True)
    print(f"[INFO] Source of truth: {brief.source_of_truth}", flush=True)

    planner_output = run_stage(
        stage_name="Product Planner Agent",
        output_path=output_dir / "planner_output.json",
        runner=lambda: run_product_planner_agent(
            ProductPlannerInput(project_brief=brief)
        ),
    )

    question_output = run_stage(
        stage_name="Question Power Designer Agent",
        output_path=output_dir / "question_output.json",
        runner=lambda: run_question_power_designer_agent(
            QuestionPowerDesignerInput(planner_output=planner_output)
        ),
    )

    quest_output = run_stage(
        stage_name="Quest Designer Agent",
        output_path=output_dir / "quest_output.json",
        runner=lambda: run_quest_designer_agent(
            QuestDesignerInput(
                planner_output=planner_output,
                question_power_output=question_output,
            )
        ),
    )

    growth_output = run_stage(
        stage_name="Growth Mapping Agent",
        output_path=output_dir / "growth_output.json",
        runner=lambda: run_growth_mapping_agent(
            GrowthMappingInput(
                question_power_output=question_output,
                quest_output=quest_output,
            )
        ),
    )

    builder_output = run_stage(
        stage_name="Builder & QA Agent",
        output_path=output_dir / "builder_qa_output.json",
        runner=lambda: run_builder_qa_agent(
            BuilderQAInput(
                planner_output=planner_output,
                question_power_output=question_output,
                quest_output=quest_output,
                growth_mapping_output=growth_output,
            )
        ),
    )

    summary_path = output_dir / "final_summary.md"
    write_final_summary(
        path=summary_path,
        brief=brief,
        planner_output=planner_output,
        question_output=question_output,
        quest_output=quest_output,
        growth_output=growth_output,
        builder_output=builder_output,
    )
    print("[SUCCESS] Final summary generated", flush=True)
    print(f"[OUTPUT] {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
