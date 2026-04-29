from __future__ import annotations

import json
from pathlib import Path

from loaders import load_input_intake
from orchestrator.app_source import build_content_filename
from orchestrator.pipeline import ImplementationPipeline
from schemas.implementation.common import LocalCheckResult
from schemas.implementation.implementation_spec import parse_markdown_spec
from schemas.planning_package import PlanningReviewItem, ValidationStatus
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_markdown_spec_extracts_expected_fields() -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")

    assert spec.service_name == "질문력 향상 퀴즈 서비스 구현 명세서"
    assert spec.target_framework == "streamlit"
    assert "중학생" in spec.target_users
    assert spec.learning_goals == ["구체성", "맥락성", "목적성"]
    assert spec.total_count == 8
    assert spec.items_per_type == 2
    assert spec.core_features == [
        "질문에서 빠진 요소 찾기",
        "더 좋은 질문 고르기",
        "모호한 질문 고치기",
        "상황에 맞는 질문 만들기",
    ]
    assert any("총 8문제" in criterion for criterion in spec.acceptance_criteria)


def test_pipeline_with_fake_llm_generates_expected_outputs(tmp_path: Path) -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    content_filename = build_content_filename(spec.service_name)
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    expected_files = [
        "spec_intake_output.json",
        "requirement_mapping_output.json",
        content_filename,
        "prototype_builder_output.json",
        "run_test_and_fix_output.json",
        "qa_alignment_output.json",
        "execution_log.txt",
        "qa_report.md",
        "change_log.md",
        "final_summary.md",
    ]
    for file_name in expected_files:
        assert (output_dir / file_name).exists(), file_name

    quiz_contents = json.loads((output_dir / content_filename).read_text(encoding="utf-8"))
    assert len(quiz_contents["quiz_types"]) == 4
    assert len(quiz_contents["items"]) == 8
    assert set(quiz_contents["quiz_types"]) == {
        "더 좋은 질문 고르기",
        "질문에서 빠진 요소 찾기",
        "모호한 질문 고치기",
        "상황에 맞는 질문 만들기",
    }
    assert all("learning_dimension" in item for item in quiz_contents["items"])
    assert quiz_contents["interaction_mode"] == "quiz"
    assert len(quiz_contents["interaction_units"]) >= len(quiz_contents["items"]) * 2
    assert quiz_contents["interaction_validation"]["structure_valid"] is True
    assert quiz_contents["semantic_validation"]["semantic_validator_passed"] is True
    assert quiz_contents["semantic_validation"]["quiz_type_distribution_valid"] is True
    assert quiz_contents["semantic_validation"]["learning_dimension_values_valid"] is True
    assert (tmp_path / "app.py").exists()
    assert "LLM_GENERATED_APP_MARKER" in (tmp_path / "app.py").read_text(encoding="utf-8")


def test_pipeline_with_planning_package_generates_service_named_contents(tmp_path: Path) -> None:
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    intake_result = load_input_intake(package_dir)
    assert intake_result.implementation_spec is not None
    implementation_spec = intake_result.implementation_spec
    content_filename = build_content_filename(implementation_spec.service_name)

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=package_dir,
        implementation_spec=implementation_spec,
        input_intake_result=intake_result,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    content_path = tmp_path / "outputs" / content_filename
    intake_report_path = tmp_path / "outputs" / "input_intake_report.json"
    final_summary = (tmp_path / "outputs" / "final_summary.md").read_text(encoding="utf-8")
    qa_report = (tmp_path / "outputs" / "qa_report.md").read_text(encoding="utf-8")
    assert intake_report_path.exists()
    assert "Input Intake" in final_summary
    assert "Input Intake" in qa_report
    assert "interaction_mode" in final_summary
    assert "interaction_units 수" in qa_report
    assert content_path.exists()
    payload = json.loads(content_path.read_text(encoding="utf-8"))
    assert len(payload["items"]) == 3
    assert set(payload["quiz_types"]) == {"multiple_choice", "question_improvement"}
    assert payload["interaction_mode"] == "quiz"
    assert payload["interaction_validation"]["structure_valid"] is True
    assert [item["quiz_type"] for item in payload["items"]] == [
        "multiple_choice",
        "question_improvement",
        "question_improvement",
    ]
    app_source = (tmp_path / "app.py").read_text(encoding="utf-8")
    assert "LLM_GENERATED_APP_MARKER" in app_source
    assert "def api_session_start()" in app_source
    assert "def api_quest_submit(user_response: Any)" in app_source
    assert "def api_session_result()" in app_source
    assert content_filename in app_source
    assert (tmp_path / "app.py").read_bytes().endswith(b"\n")


def test_pipeline_records_input_intake_planning_review_warning(tmp_path: Path) -> None:
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    intake_result = load_input_intake(package_dir)
    assert intake_result.implementation_spec is not None
    review_intake_result = intake_result.model_copy(
        update={
            "status": ValidationStatus.NEEDS_PLANNING_REVIEW,
            "planning_review_items": [
                PlanningReviewItem(
                    field_path="llm_spec.generation_prompt",
                    reason="생성 의도는 기획팀 검토가 필요합니다.",
                )
            ],
        }
    )

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=package_dir,
        implementation_spec=review_intake_result.implementation_spec,
        input_intake_result=review_intake_result,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    final_summary = (tmp_path / "outputs" / "final_summary.md").read_text(encoding="utf-8")
    qa_report = (tmp_path / "outputs" / "qa_report.md").read_text(encoding="utf-8")
    assert "## Input Intake Warning" in final_summary
    assert "## Input Intake Warning" in qa_report
    assert "llm_spec.generation_prompt" in final_summary
    assert "llm_spec.generation_prompt" in qa_report


def test_pipeline_stops_before_local_checks_for_unsupported_framework(tmp_path: Path) -> None:
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    intake_result = load_input_intake(package_dir)
    assert intake_result.implementation_spec is not None
    unsupported_spec = intake_result.implementation_spec.model_copy(
        update={"target_framework": "react"}
    )

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=package_dir,
        implementation_spec=unsupported_spec,
        input_intake_result=intake_result,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    result = pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    execution_log = (output_dir / "execution_log.txt").read_text(encoding="utf-8")
    qa_report = (output_dir / "qa_report.md").read_text(encoding="utf-8")
    final_summary = (output_dir / "final_summary.md").read_text(encoding="utf-8")

    assert result["prototype_builder_output"].is_supported is False
    assert prototype_output["target_framework"] == "react"
    assert prototype_output["is_supported"] is False
    assert "not supported yet" in prototype_output["unsupported_reason"]
    assert "[UNSUPPORTED] target_framework=react" in execution_log
    assert "py_compile" not in execution_log
    assert "local checks: NOT RUN" in qa_report
    assert "target_framework: react" in final_summary
    assert not (output_dir / "run_test_and_fix_output.json").exists()
    assert not (output_dir / "qa_alignment_output.json").exists()
    assert not (tmp_path / "app.py").exists()


def test_pipeline_records_invalid_target_framework_reason(tmp_path: Path) -> None:
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    intake_result = load_input_intake(package_dir)
    assert intake_result.implementation_spec is not None
    invalid_spec = intake_result.implementation_spec.model_copy(
        update={"target_framework": "stramlit"}
    )

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=package_dir,
        implementation_spec=invalid_spec,
        input_intake_result=intake_result,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    execution_log = (output_dir / "execution_log.txt").read_text(encoding="utf-8")

    assert prototype_output["target_framework"] == "stramlit"
    assert prototype_output["is_supported"] is False
    assert "is not recognized" in prototype_output["unsupported_reason"]
    assert "Known values: fastapi, nextjs, react, streamlit." in prototype_output["unsupported_reason"]
    assert "[UNSUPPORTED] target_framework=stramlit" in execution_log


def test_pipeline_does_not_apply_fallback_for_package_pytest_only_failure(
    tmp_path: Path,
) -> None:
    class PackagePytestFailingPipeline(ImplementationPipeline):
        def _run_package_contract_check(self):
            return LocalCheckResult(
                check_name="package_pytest",
                command="fake package pytest",
                passed=False,
                details="package contract failed",
            )

    pipeline = PackagePytestFailingPipeline(
        llm_client=FakeLLMClient(no_patch=True),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    app_source = (tmp_path / "app.py").read_text(encoding="utf-8")

    assert prototype_output["generation_mode"] == "llm_generated"
    assert prototype_output["fallback_used"] is False
    assert "FALLBACK_USED" not in prototype_output["builder_errors"]
    assert "LLM_GENERATED_APP_MARKER" in app_source


def test_pipeline_reflection_patches_streamlit_smoke_failure(tmp_path: Path) -> None:
    class SmokeFailsOncePipeline(ImplementationPipeline):
        smoke_calls = 0

        def _run_streamlit_smoke_check(self):
            self.smoke_calls += 1
            return LocalCheckResult(
                check_name="streamlit_smoke",
                command="fake streamlit smoke",
                passed=self.smoke_calls > 1,
                details="fake smoke failure" if self.smoke_calls == 1 else "fake smoke pass",
            )

    pipeline = SmokeFailsOncePipeline(
        llm_client=FakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=True,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    run_test_output = json.loads(
        (output_dir / "run_test_and_fix_output.json").read_text(encoding="utf-8")
    )
    app_source = (tmp_path / "app.py").read_text(encoding="utf-8")

    assert prototype_output["generation_mode"] == "llm_generated"
    assert prototype_output["fallback_used"] is False
    assert prototype_output["reflection_attempts"] == 1
    assert "STREAMLIT_SMOKE_FAILED" in "\n".join(run_test_output["fixes_applied"])
    assert "LLM_GENERATED_APP_MARKER" in app_source


def test_pipeline_falls_back_when_patch_is_not_available(tmp_path: Path) -> None:
    class SmokeFailsOncePipeline(ImplementationPipeline):
        smoke_calls = 0

        def _run_streamlit_smoke_check(self):
            self.smoke_calls += 1
            return LocalCheckResult(
                check_name="streamlit_smoke",
                command="fake streamlit smoke",
                passed=self.smoke_calls > 1,
                details="fake smoke failure" if self.smoke_calls == 1 else "fake smoke pass",
            )

    pipeline = SmokeFailsOncePipeline(
        llm_client=FakeLLMClient(no_patch=True),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=True,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    run_test_output = json.loads(
        (output_dir / "run_test_and_fix_output.json").read_text(encoding="utf-8")
    )
    final_summary = (output_dir / "final_summary.md").read_text(encoding="utf-8")

    assert prototype_output["generation_mode"] == "fallback_template"
    assert prototype_output["fallback_used"] is True
    assert "PATCH_FAILED" in prototype_output["builder_errors"]
    assert "FALLBACK_USED" in prototype_output["builder_errors"]
    assert "FALLBACK_USED" in "\n".join(run_test_output["fixes_applied"])
    assert "fallback_used: True" in final_summary
    assert "LLM-generated app.py는 실패했고 fallback template" in final_summary


def test_pipeline_falls_back_when_patch_still_fails(tmp_path: Path) -> None:
    class SmokeAlwaysFailsPipeline(ImplementationPipeline):
        def _run_streamlit_smoke_check(self):
            return LocalCheckResult(
                check_name="streamlit_smoke",
                command="fake streamlit smoke",
                passed=False,
                details="fake smoke failure",
            )

    pipeline = SmokeAlwaysFailsPipeline(
        llm_client=FakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=True,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    prototype_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    run_test_output = json.loads(
        (output_dir / "run_test_and_fix_output.json").read_text(encoding="utf-8")
    )

    assert prototype_output["generation_mode"] == "fallback_template"
    assert prototype_output["fallback_used"] is True
    assert prototype_output["reflection_attempts"] == 1
    assert "PATCH_FAILED" in prototype_output["builder_errors"]
    assert "FALLBACK_USED" in prototype_output["builder_errors"]
    assert "FALLBACK_USED" in "\n".join(run_test_output["fixes_applied"])
