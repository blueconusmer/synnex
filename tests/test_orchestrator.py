from __future__ import annotations

import json
from pathlib import Path

from loaders import load_input_intake
from orchestrator.app_source import build_content_filename
from orchestrator.pipeline import ImplementationPipeline
from schemas.implementation.common import FailureRecord, LocalCheckResult
from schemas.implementation.implementation_spec import parse_markdown_spec
from schemas.implementation.orchestration_decision import OrchestrationDecision, RetryInstruction
from schemas.planning_package import PlanningReviewItem, ValidationStatus
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]
QUEST_V2_PACKAGE_DIR = REPO_ROOT / "inputs" / "260429_퀘스트_v2"


def _build_coaching_spec():
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    return spec.model_copy(
        update={
            "service_name": "질문 코칭 챗봇 MVP",
            "service_purpose": "중학생 질문 코칭 챗봇 MVP를 구현한다.",
            "core_features": ["coaching_session"],
            "learning_goals": ["구체성", "맥락성", "목적성"],
            "total_count": 1,
            "items_per_type": 1,
            "content_distribution": {},
        }
    )


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
        "orchestration_decision.json",
        "retry_history.json",
        "execution_log.txt",
        "qa_report.md",
        "change_log.md",
        "final_summary.md",
    ]
    for file_name in expected_files:
        assert (output_dir / file_name).exists(), file_name

    quiz_contents = json.loads((output_dir / content_filename).read_text(encoding="utf-8"))
    orchestration_decision = json.loads(
        (output_dir / "orchestration_decision.json").read_text(encoding="utf-8")
    )
    retry_history = json.loads((output_dir / "retry_history.json").read_text(encoding="utf-8"))
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
    assert orchestration_decision["overall_status"] == "PASS"
    assert retry_history == []
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
    assert "Feedback Loop Summary" in final_summary
    assert "Feedback Loop Summary" in qa_report
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


def test_pipeline_runs_for_question_quest_v2_baseline(tmp_path: Path) -> None:
    intake_result = load_input_intake(QUEST_V2_PACKAGE_DIR)
    assert intake_result.implementation_spec is not None
    implementation_spec = intake_result.implementation_spec
    content_filename = build_content_filename(implementation_spec.service_name)
    app_target_path = tmp_path / "outputs" / "question_quest_v2" / "app.py"

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=QUEST_V2_PACKAGE_DIR,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs" / "question_quest_v2",
        implementation_spec=implementation_spec,
        input_intake_result=intake_result,
        app_target_path=app_target_path,
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs" / "question_quest_v2"
    payload = json.loads((output_dir / content_filename).read_text(encoding="utf-8"))
    builder_output = json.loads(
        (output_dir / "prototype_builder_output.json").read_text(encoding="utf-8")
    )
    final_summary = (output_dir / "final_summary.md").read_text(encoding="utf-8")
    qa_report = (output_dir / "qa_report.md").read_text(encoding="utf-8")

    assert intake_result.runtime_config.target_framework == "streamlit"
    assert payload["interaction_mode"] == "quiz"
    assert "quest" in payload["interaction_mode_reason"].lower()
    assert len(payload["interaction_units"]) >= len(payload["items"]) * 2
    assert payload["interaction_validation"]["structure_valid"] is True
    assert [item["quiz_type"] for item in payload["items"]] == [
        "multiple_choice",
        "situation_card",
        "question_improvement",
        "situation_card",
        "battle",
    ]
    assert app_target_path.exists()
    assert (output_dir / "input_intake_report.json").exists()
    assert (output_dir / "run_test_and_fix_output.json").exists()
    assert (output_dir / "qa_report.md").exists()
    assert (output_dir / "final_summary.md").exists()
    assert "interaction_mode=quiz" in final_summary
    assert "interaction_units 수 확인" in qa_report
    assert "fallback template 사용 여부" in qa_report
    assert builder_output["target_framework"] == "streamlit"


def test_feedback_router_targets_spec_intake_for_weak_spec(tmp_path: Path) -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(weak_spec_first_pass=True),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.issue_type == "SPEC_INTERPRETATION_ISSUE"
    assert decision.target_agent == "SPEC_INTAKE"
    assert decision.retry_required is True


def test_feedback_router_targets_requirement_mapping_for_weak_contract(tmp_path: Path) -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(weak_requirement_first_pass=True),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.issue_type == "REQUIREMENT_MAPPING_ISSUE"
    assert decision.target_agent == "REQUIREMENT_MAPPING"
    assert decision.retry_required is True


def test_feedback_router_targets_content_interaction_for_invalid_units(tmp_path: Path) -> None:
    spec = _build_coaching_spec()
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(invalid_content_first_pass=True),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        implementation_spec=spec,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.issue_type == "CONTENT_INTERACTION_ISSUE"
    assert decision.target_agent == "CONTENT_INTERACTION"
    assert decision.retry_required is True


def test_feedback_router_marks_code_only_runtime_failure_out_of_scope(tmp_path: Path) -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )
    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    failing_run_output = stage_outputs["run_test_and_fix_output"].model_copy(
        update={
            "failures": [
                FailureRecord(
                    check_name="py_compile",
                    summary="py_compile failed",
                    details="fake syntax error",
                )
            ],
            "checks_run": ["py_compile"],
            "remaining_risks": ["fake syntax error"],
        }
    )
    stage_outputs["run_test_and_fix_output"] = failing_run_output

    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.overall_status == "OUT_OF_SCOPE"
    assert decision.target_agent == "NONE"
    assert decision.retry_required is False


def test_feedback_router_uses_llm_judge_for_ambiguous_app_generation_feedback(
    tmp_path: Path,
) -> None:
    spec = _build_coaching_spec()
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(
            invalid_content_first_pass=True,
            invalid_app_generation=True,
            judge_target="CONTENT_INTERACTION",
        ),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        implementation_spec=spec,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.issue_type == "APP_GENERATION_FEEDBACK"
    assert decision.llm_judge_used is True
    assert decision.llm_judge_status == "SUCCESS"
    assert decision.target_agent == "CONTENT_INTERACTION"
    assert decision.retry_required is True


def test_feedback_router_falls_back_to_human_review_when_judge_fails(tmp_path: Path) -> None:
    spec = _build_coaching_spec()
    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(
            invalid_content_first_pass=True,
            invalid_app_generation=True,
            judge_fail=True,
        ),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        implementation_spec=spec,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    stage_outputs = pipeline._run_pipeline_cycle(
        spec=spec,
        content_filename=build_content_filename(spec.service_name),
        retry_contexts={},
        start_stage="SPEC_INTAKE",
        previous_outputs=None,
    )
    decision = pipeline._build_feedback_decision(
        spec=spec,
        stage_outputs=stage_outputs,
        retry_count=0,
    )

    assert decision.overall_status == "NEEDS_HUMAN_REVIEW"
    assert decision.target_agent == "HUMAN_REVIEW"
    assert decision.retry_required is False
    assert decision.llm_judge_used is True


def test_pipeline_retries_content_interaction_once_and_completes(tmp_path: Path) -> None:
    spec = _build_coaching_spec()
    fake_llm = FakeLLMClient(invalid_content_first_pass=True)
    pipeline = ImplementationPipeline(
        llm_client=fake_llm,
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        implementation_spec=spec,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    decision = json.loads((output_dir / "orchestration_decision.json").read_text(encoding="utf-8"))
    history = json.loads((output_dir / "retry_history.json").read_text(encoding="utf-8"))
    content_filename = build_content_filename(spec.service_name)
    payload = json.loads((output_dir / content_filename).read_text(encoding="utf-8"))

    assert decision["overall_status"] == "RETRY_COMPLETED"
    assert decision["retry_count"] == 1
    assert len(history) == 1
    assert history[0]["target_agent"] == "CONTENT_INTERACTION"
    assert payload["interaction_validation"]["structure_valid"] is True
    assert fake_llm.response_call_counts["ContentInteractionOutput"] == 2
    assert fake_llm.response_call_counts["SpecIntakeOutput"] == 1
    assert fake_llm.response_call_counts["RequirementMappingOutput"] == 1


def test_pipeline_stops_with_human_review_after_same_agent_repeats(tmp_path: Path) -> None:
    class AlwaysWeakSpecFakeLLMClient(FakeLLMClient):
        def generate_json(self, *, prompt: str, response_model, system_prompt=None):
            if response_model.__name__ == "SpecIntakeOutput":
                return response_model.model_validate(
                    {
                        "agent": {
                            "english_name": "Spec Intake Agent",
                            "korean_name": "구현 명세서 분석 Agent",
                        },
                        "team_identity": "교육 서비스 구현 전문 AI Agent 팀",
                        "service_summary": "짧음",
                        "normalized_requirements": [],
                        "delivery_expectations": [],
                        "acceptance_focus": [],
                    }
                )
            return super().generate_json(
                prompt=prompt,
                response_model=response_model,
                system_prompt=system_prompt,
            )

    pipeline = ImplementationPipeline(
        llm_client=AlwaysWeakSpecFakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    output_dir = tmp_path / "outputs"
    decision = json.loads((output_dir / "orchestration_decision.json").read_text(encoding="utf-8"))
    history = json.loads((output_dir / "retry_history.json").read_text(encoding="utf-8"))

    assert decision["overall_status"] == "NEEDS_HUMAN_REVIEW"
    assert decision["target_agent"] == "HUMAN_REVIEW"
    assert decision["retry_count"] == 2
    assert len(history) == 2
    assert all(entry["target_agent"] == "SPEC_INTAKE" for entry in history)


def test_pipeline_stops_after_retry_budget_three(tmp_path: Path) -> None:
    class BudgetDecisionPipeline(ImplementationPipeline):
        decision_calls = 0

        def _build_feedback_decision(self, *, spec, stage_outputs, retry_count):
            self.decision_calls += 1
            targets = [
                "SPEC_INTAKE",
                "REQUIREMENT_MAPPING",
                "CONTENT_INTERACTION",
                "SPEC_INTAKE",
            ]
            if self.decision_calls > len(targets):
                return OrchestrationDecision(
                    overall_status="PASS",
                    issue_type="NONE",
                    observed_stage="none",
                    target_agent="NONE",
                    candidate_agents=["NONE"],
                    reason="done",
                    recommended_action="done",
                    retry_required=False,
                    retry_instruction=RetryInstruction(),
                    llm_judge_used=False,
                    llm_judge_status="NOT_USED",
                    retry_count=retry_count,
                    max_retry_count=3,
                    should_stop=True,
                    stop_reason="done",
                )
            target = targets[self.decision_calls - 1]
            return OrchestrationDecision(
                overall_status="RETRY_RECOMMENDED",
                issue_type="APP_GENERATION_FEEDBACK",
                observed_stage="prototype_builder",
                target_agent=target,
                candidate_agents=[target],
                reason="budget test",
                recommended_action="retry",
                retry_required=True,
                retry_instruction=RetryInstruction(summary=f"{target} retry"),
                llm_judge_used=False,
                llm_judge_status="NOT_USED",
                retry_count=retry_count,
                max_retry_count=3,
                should_stop=False,
                stop_reason="",
            )

    pipeline = BudgetDecisionPipeline(
        llm_client=FakeLLMClient(),
        spec_path=REPO_ROOT / "inputs" / "quiz_service_spec.md",
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    decision = json.loads((tmp_path / "outputs" / "orchestration_decision.json").read_text(encoding="utf-8"))
    history = json.loads((tmp_path / "outputs" / "retry_history.json").read_text(encoding="utf-8"))

    assert decision["overall_status"] == "NEEDS_HUMAN_REVIEW"
    assert decision["retry_count"] == 3
    assert len(history) == 3
