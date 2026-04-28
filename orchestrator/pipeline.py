from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from agents.implementation.content_interaction_agent import run_content_interaction_agent
from agents.implementation.prototype_builder_agent import (
    FALLBACK_USED,
    build_fallback_app_source,
    run_prototype_builder_agent,
)
from agents.implementation.qa_alignment_agent import run_qa_alignment_agent
from agents.implementation.requirement_mapping_agent import run_requirement_mapping_agent
from agents.implementation.run_test_and_fix_agent import run_run_test_and_fix_agent
from agents.implementation.spec_intake_agent import run_spec_intake_agent
from clients.llm import LLMClient
from orchestrator.app_source import build_content_filename
from schemas.implementation.common import LocalCheckResult, SchemaModel
from schemas.implementation.content_interaction import ContentInteractionInput
from schemas.implementation.implementation_spec import ImplementationSpec, parse_markdown_spec
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.qa_alignment import QAAlignmentInput
from schemas.implementation.requirement_mapping import RequirementMappingInput
from schemas.implementation.run_test_and_fix import RunTestAndFixInput
from schemas.implementation.spec_intake import SpecIntakeInput
from schemas.planning_package import InputIntakeResult, ValidationStatus


class ImplementationPipeline:
    """Sequential pipeline for the 6-agent education-service implementation flow."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        spec_path: Path,
        workspace_dir: Path,
        output_dir: Path,
        implementation_spec: ImplementationSpec | None = None,
        input_intake_result: InputIntakeResult | None = None,
        app_target_path: Path | None = None,
        python_executable: str | None = None,
        enable_streamlit_smoke: bool = True,
    ) -> None:
        self.llm_client = llm_client
        self.spec_path = spec_path
        self.workspace_dir = workspace_dir
        self.output_dir = output_dir
        self.implementation_spec = implementation_spec
        self.input_intake_result = input_intake_result
        self.app_target_path = app_target_path or workspace_dir / "app.py"
        self.python_executable = python_executable or sys.executable
        self.enable_streamlit_smoke = enable_streamlit_smoke
        self.logs: list[str] = []

    def run(self) -> dict[str, SchemaModel]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        spec = self.implementation_spec or parse_markdown_spec(self.spec_path)
        content_filename = build_content_filename(spec.service_name)
        self._log("[INFO] Starting education-service implementation pipeline")
        self._log(f"[INFO] Source spec: {self.spec_path}")
        if self.input_intake_result is not None:
            self._save_json(self.output_dir / "input_intake_report.json", self.input_intake_result)
            self._log(f"[INFO] Input intake status: {self.input_intake_result.status.value}")

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
            output_name=content_filename,
            runner=lambda: run_content_interaction_agent(
                ContentInteractionInput(
                    spec_intake_output=spec_intake_output,
                    requirement_mapping_output=requirement_mapping_output,
                    implementation_spec=spec,
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
                    implementation_spec=spec,
                ),
                self.llm_client,
            ),
        )
        self._normalize_prototype_builder_output(
            prototype_builder_output,
            service_name=spec.service_name,
            content_filename=content_filename,
        )
        self._save_json(
            self.output_dir / "prototype_builder_output.json",
            prototype_builder_output,
        )
        if not prototype_builder_output.is_supported:
            return self._finish_unsupported_framework(
                spec=spec,
                spec_intake_output=spec_intake_output,
                requirement_mapping_output=requirement_mapping_output,
                content_interaction_output=content_interaction_output,
                prototype_builder_output=prototype_builder_output,
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
        self._annotate_failure_codes(run_test_and_fix_output, local_checks)

        if run_test_and_fix_output.patched_files and run_test_and_fix_output.should_retry_builder:
            prototype_builder_output.reflection_attempts += 1
            self._save_json(
                self.output_dir / "prototype_builder_output.json",
                prototype_builder_output,
            )
            self._materialize_patched_files(run_test_and_fix_output.patched_files)
            local_checks = self._run_local_checks()
            first_attempt_output = run_test_and_fix_output
            run_test_and_fix_output = run_run_test_and_fix_agent(
                RunTestAndFixInput(
                    prototype_builder_output=prototype_builder_output,
                    check_results=local_checks,
                ),
                self.llm_client,
            )
            self._annotate_failure_codes(run_test_and_fix_output, local_checks)
            run_test_and_fix_output.fixes_applied = _dedupe_preserve_order(
                [
                    *first_attempt_output.fixes_applied,
                    *run_test_and_fix_output.fixes_applied,
                ]
            )
            run_test_and_fix_output.remaining_risks = _dedupe_preserve_order(
                [
                    *first_attempt_output.remaining_risks,
                    *run_test_and_fix_output.remaining_risks,
                ]
            )
            self._save_json(
                self.output_dir / "run_test_and_fix_output.json",
                run_test_and_fix_output,
            )

        if self._has_failed_checks(local_checks):
            run_test_and_fix_output = self._apply_fallback_template_after_reflection(
                spec_intake_output=spec_intake_output,
                requirement_mapping_output=requirement_mapping_output,
                content_interaction_output=content_interaction_output,
                implementation_spec=spec,
                prototype_builder_output=prototype_builder_output,
                previous_run_test_and_fix_output=run_test_and_fix_output,
                failed_checks=local_checks,
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
                    implementation_spec=spec,
                ),
                self.llm_client,
            ),
        )

        self._write_execution_log()
        self._write_change_log(qa_alignment_output.change_log_entries)
        self._write_qa_report(qa_alignment_output)
        self._write_final_summary(
            spec,
            spec_intake_output.service_summary,
            requirement_mapping_output.implementation_targets,
            content_interaction_output,
            prototype_builder_output,
            run_test_and_fix_output,
            qa_alignment_output.final_summary_points,
        )

        return {
            "input_intake_result": self.input_intake_result,
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

    def _normalize_prototype_builder_output(
        self,
        output,
        *,
        service_name: str,
        content_filename: str,
    ) -> None:
        output.service_name = service_name
        if not output.is_supported:
            return

        output.runtime_notes = _dedupe_preserve_order(
            [
                *output.runtime_notes,
                f"app.py는 outputs/{content_filename}을 읽는다.",
                "streamlit run app.py로 실행한다.",
            ]
        )
        output.integration_notes = _dedupe_preserve_order(
            [
                *output.integration_notes,
                f"{content_filename}이 outputs/ 아래에 존재해야 한다.",
            ]
        )
        for generated_file in output.generated_files:
            if Path(generated_file.path).name == "app.py":
                generated_file.description = (
                    f"{service_name} 콘텐츠를 읽는 self-contained Streamlit MVP app."
                )

    def _finish_unsupported_framework(
        self,
        *,
        spec: ImplementationSpec,
        spec_intake_output,
        requirement_mapping_output,
        content_interaction_output,
        prototype_builder_output,
    ) -> dict[str, SchemaModel]:
        reason = (
            prototype_builder_output.unsupported_reason
            or "Requested target_framework is not supported yet."
        )
        self._log(
            "[UNSUPPORTED] "
            f"target_framework={prototype_builder_output.target_framework}: {reason}"
        )
        self._write_execution_log()
        self._write_unsupported_change_log(prototype_builder_output)
        self._write_unsupported_qa_report(prototype_builder_output)
        self._write_unsupported_final_summary(
            spec=spec,
            service_summary=spec_intake_output.service_summary,
            implementation_targets=requirement_mapping_output.implementation_targets,
            content_output=content_interaction_output,
            prototype_builder_output=prototype_builder_output,
        )
        return {
            "input_intake_result": self.input_intake_result,
            "spec_intake_output": spec_intake_output,
            "requirement_mapping_output": requirement_mapping_output,
            "quiz_contents": content_interaction_output,
            "prototype_builder_output": prototype_builder_output,
        }

    def _materialize_generated_files(self, generated_files) -> None:
        for generated_file in generated_files:
            target_path = self.workspace_dir / generated_file.path
            if Path(generated_file.path).name == "app.py":
                target_path = self.app_target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(_ensure_trailing_newline(generated_file.content), encoding="utf-8")
            self._log(f"[MATERIALIZED] {target_path}")

    def _materialize_patched_files(self, patched_files) -> None:
        for patched_file in patched_files:
            target_path = self.workspace_dir / patched_file.path
            if Path(patched_file.path).name == "app.py":
                target_path = self.app_target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(_ensure_trailing_newline(patched_file.content), encoding="utf-8")
            self._log(f"[PATCHED] {target_path}")

    def _apply_fallback_template_after_reflection(
        self,
        *,
        spec_intake_output,
        requirement_mapping_output,
        content_interaction_output,
        implementation_spec: ImplementationSpec,
        prototype_builder_output,
        previous_run_test_and_fix_output,
        failed_checks: list[LocalCheckResult],
    ):
        failure_codes = self._failure_codes_for_checks(failed_checks)
        fallback_reason = (
            "PATCH_FAILED: local checks still failed after the allowed reflection attempt."
            if prototype_builder_output.reflection_attempts
            else "PATCH_FAILED: no valid patch was produced for failed local checks."
        )
        self._log(f"[FALLBACK] {fallback_reason}")

        fallback_source = build_fallback_app_source(
            PrototypeBuilderInput(
                spec_intake_output=spec_intake_output,
                requirement_mapping_output=requirement_mapping_output,
                content_interaction_output=content_interaction_output,
                implementation_spec=implementation_spec,
            )
        )
        prototype_builder_output.generation_mode = "fallback_template"
        prototype_builder_output.fallback_used = True
        prototype_builder_output.fallback_reason = fallback_reason
        prototype_builder_output.builder_errors = _dedupe_preserve_order(
            [
                *prototype_builder_output.builder_errors,
                *failure_codes,
                "PATCH_FAILED",
                FALLBACK_USED,
            ]
        )
        for generated_file in prototype_builder_output.generated_files:
            if Path(generated_file.path).name == "app.py":
                generated_file.content = fallback_source
                generated_file.description = (
                    "Deterministic Streamlit fallback app used after LLM/patch failure."
                )
                break
        else:
            from schemas.implementation.common import GeneratedFile

            prototype_builder_output.generated_files.append(
                GeneratedFile(
                    path="app.py",
                    description="Deterministic Streamlit fallback app used after LLM/patch failure.",
                    content=fallback_source,
                )
            )
        prototype_builder_output.runtime_notes = _dedupe_preserve_order(
            [
                *prototype_builder_output.runtime_notes,
                "LLM-generated app.py 또는 patch 결과가 실패해 fallback template을 적용했다.",
            ]
        )
        prototype_builder_output.integration_notes = _dedupe_preserve_order(
            [
                *prototype_builder_output.integration_notes,
                "Fallback template 사용은 LLM-generated app.py 성공으로 기록하지 않는다.",
            ]
        )
        self._save_json(
            self.output_dir / "prototype_builder_output.json",
            prototype_builder_output,
        )
        self._materialize_generated_files(prototype_builder_output.generated_files)
        fallback_checks = self._run_local_checks()
        fallback_run_output = run_run_test_and_fix_agent(
            RunTestAndFixInput(
                prototype_builder_output=prototype_builder_output,
                check_results=fallback_checks,
            ),
            self.llm_client,
        )
        self._annotate_failure_codes(fallback_run_output, fallback_checks)
        fallback_run_output.fixes_applied = _dedupe_preserve_order(
            [
                *previous_run_test_and_fix_output.fixes_applied,
                f"{FALLBACK_USED}: {fallback_reason}",
                *fallback_run_output.fixes_applied,
            ]
        )
        fallback_run_output.remaining_risks = _dedupe_preserve_order(
            [
                *previous_run_test_and_fix_output.remaining_risks,
                *fallback_run_output.remaining_risks,
                (
                    "LLM-generated app.py는 최종 local checks를 통과하지 못했고 "
                    "fallback template으로 실행 가능 상태를 확보했다."
                ),
            ]
        )
        self._save_json(
            self.output_dir / "run_test_and_fix_output.json",
            fallback_run_output,
        )
        return fallback_run_output

    def _run_local_checks(self) -> list[LocalCheckResult]:
        checks = [self._run_py_compile_check()]
        package_pytest_check = self._run_package_contract_check()
        if package_pytest_check is not None:
            checks.append(package_pytest_check)
        if self.enable_streamlit_smoke:
            checks.append(self._run_streamlit_smoke_check())
        return checks

    @staticmethod
    def _has_failed_checks(checks: list[LocalCheckResult]) -> bool:
        return any(not check.passed for check in checks)

    @staticmethod
    def _failure_codes_for_checks(checks: list[LocalCheckResult]) -> list[str]:
        codes: list[str] = []
        for check in checks:
            if check.passed:
                continue
            if check.check_name == "py_compile":
                codes.append("APP_PY_COMPILE_FAILED")
            elif check.check_name == "streamlit_smoke":
                codes.append("STREAMLIT_SMOKE_FAILED")
            else:
                codes.append(f"{check.check_name.upper()}_FAILED")
        return codes

    def _annotate_failure_codes(self, run_output, checks: list[LocalCheckResult]) -> None:
        failure_codes = self._failure_codes_for_checks(checks)
        if not failure_codes:
            return
        run_output.fixes_applied = _dedupe_preserve_order(
            [
                *run_output.fixes_applied,
                "Failure codes observed: " + ", ".join(failure_codes),
            ]
        )

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

    def _run_package_contract_check(self) -> LocalCheckResult | None:
        package_pytest = Path(self.spec_path) / "pytest.py"
        if not package_pytest.exists():
            return None

        command = (
            f"{self.python_executable} -m pytest --import-mode=importlib "
            f"{package_pytest} -q"
        )
        result = subprocess.run(
            [
                self.python_executable,
                "-m",
                "pytest",
                "--import-mode=importlib",
                str(package_pytest),
                "-q",
            ],
            cwd=self.workspace_dir,
            capture_output=True,
            text=True,
        )
        details = (result.stdout + "\n" + result.stderr).strip()
        self._log(
            "[CHECK] package_pytest -> "
            f"{'PASS' if result.returncode == 0 else 'FAIL'}"
        )
        return LocalCheckResult(
            check_name="package_pytest",
            command=command,
            passed=result.returncode == 0,
            details=details or "Package pytest check completed without output.",
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

    def _write_unsupported_change_log(self, prototype_builder_output) -> None:
        lines = [
            "# Change Log",
            "",
            (
                "- Prototype Builder stopped before materialization because "
                f"target_framework={prototype_builder_output.target_framework} is unsupported."
            ),
            f"- Reason: {prototype_builder_output.unsupported_reason}",
            "- Local checks, Run Test And Fix, and QA Alignment stages were not executed.",
        ]
        (self.output_dir / "change_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_unsupported_qa_report(self, prototype_builder_output) -> None:
        lines = [
            "# QA Report",
            "",
            "- Alignment status: UNSUPPORTED",
        ]
        if self.input_intake_result is not None:
            lines.extend(
                [
                    "",
                    "## Input Intake",
                    f"- Status: {self.input_intake_result.status.value}",
                    f"- Auto fixes: {len(self.input_intake_result.auto_fixes)}",
                    f"- Planning review items: {len(self.input_intake_result.planning_review_items)}",
                    f"- Issues: {len(self.input_intake_result.issues)}",
                ]
            )
        lines.extend(
            [
                "",
                "## Unsupported Framework",
                f"- target_framework: {prototype_builder_output.target_framework}",
                f"- reason: {prototype_builder_output.unsupported_reason}",
                "- local checks: NOT RUN",
            ]
        )
        (self.output_dir / "qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_unsupported_final_summary(
        self,
        *,
        spec: ImplementationSpec,
        service_summary: str,
        implementation_targets: list[str],
        content_output,
        prototype_builder_output,
    ) -> None:
        lines = [
            "# Final Summary",
            "",
            "## 서비스 요약",
            f"- {service_summary}",
            "",
            "## Framework 결과",
            f"- target_framework: {prototype_builder_output.target_framework}",
            "- 지원 여부: UNSUPPORTED",
            f"- 이유: {prototype_builder_output.unsupported_reason}",
            "- app.py materialize: NOT RUN",
            "- local checks: NOT RUN",
        ]
        if self.input_intake_result is not None:
            lines.extend(
                [
                    "",
                    "## Input Intake 결과",
                    f"- 상태: {self.input_intake_result.status.value}",
                    f"- target_framework: {self.input_intake_result.runtime_config.target_framework if self.input_intake_result.runtime_config else spec.target_framework}",
                ]
            )
        lines.extend(["", "## 구현 요구사항 요약"])
        lines.extend(f"- {target}" for target in implementation_targets)
        lines.extend(
            [
                "",
                "## 콘텐츠 생성 요약",
                f"- 퀴즈 유형 수: {len(content_output.quiz_types)}",
                f"- 총 문제 수: {len(content_output.items)}",
            ]
        )
        (self.output_dir / "final_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_qa_report(self, qa_output) -> None:
        lines = [
            "# QA Report",
            "",
            f"- Alignment status: {qa_output.alignment_status}",
        ]
        if self.input_intake_result is not None:
            lines.extend(
                [
                    "",
                    "## Input Intake",
                    f"- Status: {self.input_intake_result.status.value}",
                    f"- Auto fixes: {len(self.input_intake_result.auto_fixes)}",
                    f"- Planning review items: {len(self.input_intake_result.planning_review_items)}",
                    f"- Issues: {len(self.input_intake_result.issues)}",
                ]
            )
            if self.input_intake_result.runtime_config is not None:
                distribution = self.input_intake_result.runtime_config.content_distribution
                lines.append(f"- Content distribution: {distribution.item_count_by_type}")
            if self.input_intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW:
                lines.extend(["", "## Input Intake Warning"])
                lines.extend(
                    f"- {item.field_path}: {item.reason}"
                    for item in self.input_intake_result.planning_review_items
                )
        lines.extend(["", "## Checklist"])
        lines.extend(f"- {item}" for item in qa_output.qa_checklist)
        lines.extend(["", "## Issues"])
        if qa_output.qa_issues:
            lines.extend(f"- {issue}" for issue in qa_output.qa_issues)
        else:
            lines.append("- No blocking QA issues were reported.")
        (self.output_dir / "qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_final_summary(
        self,
        implementation_spec: ImplementationSpec,
        service_summary: str,
        implementation_targets: list[str],
        content_output,
        prototype_builder_output,
        run_test_and_fix_output,
        final_summary_points: list[str],
    ) -> None:
        quiz_types = content_output.quiz_types
        total_items = len(content_output.items)
        semantic_summary = content_output.semantic_validation
        streamlit_smoke_ran = "streamlit_smoke" in run_test_and_fix_output.checks_run
        streamlit_smoke_failed = any(
            failure.check_name == "streamlit_smoke"
            for failure in run_test_and_fix_output.failures
        )
        package_pytest_ran = "package_pytest" in run_test_and_fix_output.checks_run
        package_pytest_failed = any(
            failure.check_name == "package_pytest"
            for failure in run_test_and_fix_output.failures
        )
        lines = [
            "# Final Summary",
            "",
            "## 서비스 요약",
            f"- {service_summary}",
        ]
        if self.input_intake_result is not None:
            lines.extend(
                [
                    "",
                    "## Input Intake 결과",
                    f"- 상태: {self.input_intake_result.status.value}",
                    f"- 자동 보정: {len(self.input_intake_result.auto_fixes)}건",
                    f"- 기획팀 검토 필요: {len(self.input_intake_result.planning_review_items)}건",
                    f"- 이슈: {len(self.input_intake_result.issues)}건",
                ]
            )
            if self.input_intake_result.runtime_config is not None:
                distribution = self.input_intake_result.runtime_config.content_distribution
                lines.append(f"- 생성 단위 분포: {distribution.item_count_by_type}")
            if self.input_intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW:
                lines.extend(["", "## Input Intake Warning"])
                lines.extend(
                    f"- {item.field_path}: {item.reason}"
                    for item in self.input_intake_result.planning_review_items
                )
        lines.extend(["", "## 구현 요구사항 요약"])
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
        lines.extend(
            [
                "",
                "## Prototype Builder 결과",
                f"- target_framework: {prototype_builder_output.target_framework}",
                f"- generation_mode: {prototype_builder_output.generation_mode}",
                f"- fallback_used: {prototype_builder_output.fallback_used}",
                f"- reflection_attempts: {prototype_builder_output.reflection_attempts}",
            ]
        )
        if prototype_builder_output.fallback_used:
            lines.append(f"- fallback_reason: {prototype_builder_output.fallback_reason}")
            lines.append(
                "- LLM-generated app.py는 실패했고 fallback template으로 실행 가능 상태를 확보했다."
            )
        if prototype_builder_output.builder_errors:
            lines.append(
                "- builder_errors: " + ", ".join(prototype_builder_output.builder_errors)
            )
        if semantic_summary is not None:
            expected_type_count = len(
                implementation_spec.core_features or quiz_types
            )
            lines.extend(
                [
                    "",
                    "## #12 검증 결과",
                    (
                        f"- 총 {implementation_spec.total_count}문항 여부: "
                        f"{'PASS' if semantic_summary.total_items == implementation_spec.total_count else 'FAIL'}"
                    ),
                    (
                        f"- configured content type 수({expected_type_count}) 일치 여부: "
                        f"{'PASS' if semantic_summary.quiz_type_distribution_valid else 'FAIL'}"
                    ),
                    (
                        "- learning_dimension 허용값 여부: "
                        f"{'PASS' if semantic_summary.learning_dimension_values_valid else 'FAIL'}"
                    ),
                    (
                        "- semantic validator 통과 여부: "
                        f"{'PASS' if semantic_summary.semantic_validator_passed else 'FAIL'}"
                    ),
                    (
                        "- 재생성 발생 여부: "
                        f"{'YES' if semantic_summary.regeneration_requested else 'NO'}"
                    ),
                    (
                        "- app.py Streamlit smoke test 여부: "
                        f"{'PASS' if streamlit_smoke_ran and not streamlit_smoke_failed else 'FAIL'}"
                    ),
                    (
                        "- package pytest.py 통과 여부: "
                        f"{'PASS' if package_pytest_ran and not package_pytest_failed else 'FAIL' if package_pytest_ran else 'NOT RUN'}"
                    ),
                ]
            )
        lines.extend(["", "## 최종 요약 포인트"])
        lines.extend(f"- {point}" for point in final_summary_points)
        (self.output_dir / "final_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _log(self, message: str) -> None:
        self.logs.append(message)
        print(message, flush=True)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _ensure_trailing_newline(content: str) -> str:
    return content if content.endswith("\n") else f"{content}\n"
