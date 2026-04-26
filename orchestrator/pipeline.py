from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from agents.implementation.content_interaction_agent import run_content_interaction_agent
from agents.implementation.prototype_builder_agent import run_prototype_builder_agent
from agents.implementation.qa_alignment_agent import run_qa_alignment_agent
from agents.implementation.requirement_mapping_agent import run_requirement_mapping_agent
from agents.implementation.run_test_and_fix_agent import run_run_test_and_fix_agent
from agents.implementation.spec_intake_agent import run_spec_intake_agent
from clients.llm import LLMClient
from schemas.implementation.common import LocalCheckResult, SchemaModel
from schemas.implementation.content_interaction import ContentInteractionInput
from schemas.implementation.implementation_spec import parse_markdown_spec
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.qa_alignment import QAAlignmentInput
from schemas.implementation.requirement_mapping import RequirementMappingInput
from schemas.implementation.run_test_and_fix import RunTestAndFixInput
from schemas.implementation.spec_intake import SpecIntakeInput


class ImplementationPipeline:
    """Sequential pipeline for the 6-agent education-service implementation flow."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        spec_path: Path,
        workspace_dir: Path,
        output_dir: Path,
        app_target_path: Path | None = None,
        python_executable: str | None = None,
        enable_streamlit_smoke: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.spec_path = spec_path
        self.workspace_dir = workspace_dir
        self.output_dir = output_dir
        self.app_target_path = app_target_path or workspace_dir / "app.py"
        self.python_executable = python_executable or sys.executable
        self.enable_streamlit_smoke = enable_streamlit_smoke
        self.logs: list[str] = []

    def run(self) -> dict[str, SchemaModel]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        spec = parse_markdown_spec(self.spec_path)
        self._log("[INFO] Starting education-service implementation pipeline")
        self._log(f"[INFO] Source spec: {self.spec_path}")

        spec_intake_output = self._run_stage(
            stage_title="Spec Intake Agent / 구현 명세서 분석 Agent",
            output_name="spec_intake_output.json",
            runner=lambda: run_spec_intake_agent(
                SpecIntakeInput(implementation_spec=spec),
                self.llm_client,
            ),
        )

        requirement_mapping_output = self._run_stage(
            stage_title="Requirement Mapping Agent / 구현 요구사항 정리 Agent",
            output_name="requirement_mapping_output.json",
            runner=lambda: run_requirement_mapping_agent(
                RequirementMappingInput(spec_intake_output=spec_intake_output),
                self.llm_client,
            ),
        )

        content_interaction_output = self._run_stage(
            stage_title="Content & Interaction Agent / 교육 콘텐츠·상호작용 생성 Agent",
            output_name="quiz_contents.json",
            runner=lambda: run_content_interaction_agent(
                ContentInteractionInput(
                    spec_intake_output=spec_intake_output,
                    requirement_mapping_output=requirement_mapping_output,
                ),
                self.llm_client,
            ),
        )

        prototype_builder_output = self._run_stage(
            stage_title="Prototype Builder Agent / MVP 서비스 코드 생성 Agent",
            output_name="prototype_builder_output.json",
            runner=lambda: run_prototype_builder_agent(
                PrototypeBuilderInput(
                    spec_intake_output=spec_intake_output,
                    requirement_mapping_output=requirement_mapping_output,
                    content_interaction_output=content_interaction_output,
                ),
                self.llm_client,
            ),
        )
        self._materialize_generated_files(prototype_builder_output.generated_files)

        local_checks = self._run_local_checks()
        run_test_and_fix_output = self._run_stage(
            stage_title="Run Test And Fix Agent / 실행·테스트·수정 Agent",
            output_name="run_test_and_fix_output.json",
            runner=lambda: run_run_test_and_fix_agent(
                RunTestAndFixInput(
                    prototype_builder_output=prototype_builder_output,
                    check_results=local_checks,
                ),
                self.llm_client,
            ),
        )

        if run_test_and_fix_output.patched_files and run_test_and_fix_output.should_retry_builder:
            self._materialize_patched_files(run_test_and_fix_output.patched_files)
            local_checks = self._run_local_checks()
            run_test_and_fix_output = run_run_test_and_fix_agent(
                RunTestAndFixInput(
                    prototype_builder_output=prototype_builder_output,
                    check_results=local_checks,
                ),
                self.llm_client,
            )
            self._save_json(
                self.output_dir / "run_test_and_fix_output.json",
                run_test_and_fix_output,
            )

        qa_alignment_output = self._run_stage(
            stage_title="QA & Alignment Agent / 최종 검수·정합성 확인 Agent",
            output_name="qa_alignment_output.json",
            runner=lambda: run_qa_alignment_agent(
                QAAlignmentInput(
                    spec_intake_output=spec_intake_output,
                    requirement_mapping_output=requirement_mapping_output,
                    content_interaction_output=content_interaction_output,
                    prototype_builder_output=prototype_builder_output,
                    run_test_and_fix_output=run_test_and_fix_output,
                ),
                self.llm_client,
            ),
        )

        self._write_execution_log()
        self._write_change_log(qa_alignment_output.change_log_entries)
        self._write_qa_report(qa_alignment_output)
        self._write_final_summary(
            spec_intake_output.service_summary,
            requirement_mapping_output.implementation_targets,
            content_interaction_output.quiz_types,
            len(content_interaction_output.items),
            qa_alignment_output.final_summary_points,
        )

        return {
            "spec_intake_output": spec_intake_output,
            "requirement_mapping_output": requirement_mapping_output,
            "quiz_contents": content_interaction_output,
            "prototype_builder_output": prototype_builder_output,
            "run_test_and_fix_output": run_test_and_fix_output,
            "qa_alignment_output": qa_alignment_output,
        }

    def _run_stage(self, *, stage_title: str, output_name: str, runner) -> SchemaModel:
        self._log(f"[RUNNING] {stage_title}")
        result = runner()
        output_path = self.output_dir / output_name
        self._save_json(output_path, result)
        self._log(f"[SUCCESS] {stage_title}")
        self._log(f"[OUTPUT] {output_path}")
        return result

    def _save_json(self, path: Path, model: SchemaModel) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _materialize_generated_files(self, generated_files) -> None:
        for generated_file in generated_files:
            target_path = self.workspace_dir / generated_file.path
            if Path(generated_file.path).name == "app.py":
                target_path = self.app_target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(generated_file.content, encoding="utf-8")
            self._log(f"[MATERIALIZED] {target_path}")

    def _materialize_patched_files(self, patched_files) -> None:
        for patched_file in patched_files:
            target_path = self.workspace_dir / patched_file.path
            if Path(patched_file.path).name == "app.py":
                target_path = self.app_target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(patched_file.content, encoding="utf-8")
            self._log(f"[PATCHED] {target_path}")

    def _run_local_checks(self) -> list[LocalCheckResult]:
        checks = [self._run_py_compile_check()]
        if self.enable_streamlit_smoke:
            checks.append(self._run_streamlit_smoke_check())
        return checks

    def _run_py_compile_check(self) -> LocalCheckResult:
        command = f"{self.python_executable} -m py_compile {self.app_target_path}"
        result = subprocess.run(
            [self.python_executable, "-m", "py_compile", str(self.app_target_path)],
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
        )
        details = (result.stdout + "\n" + result.stderr).strip()
        self._log(f"[CHECK] py_compile -> {'PASS' if result.returncode == 0 else 'FAIL'}")
        return LocalCheckResult(
            check_name="py_compile",
            command=command,
            passed=result.returncode == 0,
            details=details or "py_compile completed without output.",
        )

    def _run_streamlit_smoke_check(self) -> LocalCheckResult:
        command = (
            f"{self.python_executable} -m streamlit run {self.app_target_path} "
            "--server.headless true --server.port 8765"
        )
        env = os.environ.copy()
        env["BROWSER_GATHER_USAGE_STATS"] = "false"
        process = subprocess.Popen(
            [
                self.python_executable,
                "-m",
                "streamlit",
                "run",
                str(self.app_target_path),
                "--server.headless",
                "true",
                "--server.port",
                "8765",
            ],
            cwd=self.workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        time.sleep(3)
        still_running = process.poll() is None
        output = ""
        if still_running:
            process.terminate()
            try:
                output = process.communicate(timeout=5)[0]
            except subprocess.TimeoutExpired:
                process.kill()
                output = process.communicate()[0]
        else:
            output = process.communicate()[0]

        passed = still_running and "Traceback" not in output
        self._log(f"[CHECK] streamlit_smoke -> {'PASS' if passed else 'FAIL'}")
        return LocalCheckResult(
            check_name="streamlit_smoke",
            command=command,
            passed=passed,
            details=output.strip() or "Streamlit smoke test produced no console output.",
        )

    def _write_execution_log(self) -> None:
        (self.output_dir / "execution_log.txt").write_text(
            "\n".join(self.logs) + "\n",
            encoding="utf-8",
        )

    def _write_change_log(self, entries: list[str]) -> None:
        lines = ["# Change Log", ""]
        if not entries:
            lines.append("- No additional implementation changes were required during execution.")
        else:
            lines.extend(f"- {entry}" for entry in entries)
        (self.output_dir / "change_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_qa_report(self, qa_output) -> None:
        lines = [
            "# QA Report",
            "",
            f"- Alignment status: {qa_output.alignment_status}",
            "",
            "## Checklist",
        ]
        lines.extend(f"- {item}" for item in qa_output.qa_checklist)
        lines.extend(["", "## Issues"])
        if qa_output.qa_issues:
            lines.extend(f"- {issue}" for issue in qa_output.qa_issues)
        else:
            lines.append("- No blocking QA issues were reported.")
        (self.output_dir / "qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_final_summary(
        self,
        service_summary: str,
        implementation_targets: list[str],
        quiz_types: list[str],
        total_items: int,
        final_summary_points: list[str],
    ) -> None:
        lines = [
            "# Final Summary",
            "",
            "## 서비스 요약",
            f"- {service_summary}",
            "",
            "## 구현 요구사항 요약",
        ]
        lines.extend(f"- {target}" for target in implementation_targets)
        lines.extend(
            [
                "",
                "## 콘텐츠 생성 요약",
                f"- 퀴즈 유형 수: {len(quiz_types)}",
                f"- 총 문제 수: {total_items}",
            ]
        )
        lines.extend(f"- 유형: {quiz_type}" for quiz_type in quiz_types)
        lines.extend(["", "## 최종 요약 포인트"])
        lines.extend(f"- {point}" for point in final_summary_points)
        (self.output_dir / "final_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _log(self, message: str) -> None:
        self.logs.append(message)
        print(message, flush=True)
