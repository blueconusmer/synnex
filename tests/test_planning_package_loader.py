from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from loaders import load_input_intake, load_planning_package, planning_package_to_implementation_spec
import main as main_module
from main import build_parser
from orchestrator.app_source import build_content_filename
from orchestrator.pipeline import ImplementationPipeline
from schemas.planning_package import ValidationStatus
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
CHATBOT_PACKAGE_DIR = REPO_ROOT / "inputs" / "260428_챗봇"


def test_load_planning_package_reads_fixture_files() -> None:
    package = load_planning_package(PACKAGE_DIR)

    assert package.service_meta.service_name == "question_quest"
    assert package.service_meta.target_framework == "streamlit"
    assert package.service_meta.version == "v0"
    assert package.evaluation_spec.rubric_criteria == ["구체성", "맥락성", "목적성"]
    assert package.evaluation_spec.grade_levels == ["브론즈", "실버", "골드", "플래티넘"]
    assert package.evaluation_spec.score_rules["rubric_grades"] == ["우수", "양호", "미흡"]
    assert package.evaluation_spec.score_rules["service_grades"]["플래티넘"] == [600, None]
    assert package.content_spec.total_count == 3
    assert package.content_spec.items_per_type == 2
    assert package.interface_spec.screens == ["S0", "S1", "S2", "S3", "S4", "S5"]
    assert package.interface_spec.api_endpoints == [
        "/api/session/start",
        "/api/quest/submit",
        "/api/session/result",
    ]
    assert package.llm_spec.generation_prompt
    assert package.llm_spec.evaluation_prompt


def test_load_planning_package_reads_chatbot_fixture_with_generic_fallbacks() -> None:
    package = load_planning_package(CHATBOT_PACKAGE_DIR)

    assert package.service_meta.service_name == "Question Coaching Chatbot"
    assert package.content_spec.content_types == [
        "need_specificity",
        "need_context",
        "need_purpose",
        "completed",
    ]
    assert package.content_spec.total_count == 4
    assert package.interface_spec.screens == [
        "질문 입력 화면",
        "되묻기 화면 (mode: `need_specificity` / `need_context` / `need_purpose`)",
        "재요청 결과 화면 (mode: `completed`)",
    ]
    assert package.interface_spec.api_endpoints == ["/api/chat"]
    assert package.interaction_spec.session_structure == [
        "awaiting_input",
        "diagnosing",
        "need_specificity",
        "need_context",
        "need_purpose",
        "completed",
        "error",
    ]
    assert package.llm_spec.generation_prompt


def test_loader_raises_on_malformed_data_schema_json(tmp_path: Path) -> None:
    package_dir = tmp_path / "example_service_v1"
    package_dir.mkdir()
    (package_dir / "constitution.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "data_schema.json").write_text("{not-json", encoding="utf-8")
    (package_dir / "state_machine.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "prompt_spec.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "interface_spec.md").write_text("# Empty\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_planning_package(package_dir)

    intake_result = load_input_intake(package_dir)
    assert intake_result.status == ValidationStatus.FAIL
    assert intake_result.issues[0].code == "PLANNING_PACKAGE_PARSE_FAILED"


def test_load_planning_package_treats_pytest_as_optional(tmp_path: Path) -> None:
    package_dir = tmp_path / "no_pytest_service_v0"
    shutil.copytree(PACKAGE_DIR, package_dir)
    (package_dir / "pytest.py").unlink()

    package = load_planning_package(package_dir)
    intake_result = load_input_intake(package_dir)

    assert package.test_spec.test_file_path == ""
    assert package.test_spec.acceptance_criteria == []
    assert intake_result.status == ValidationStatus.AUTO_FIXED
    assert intake_result.implementation_spec is not None
    assert intake_result.implementation_spec.acceptance_criteria == []
    assert not any(path.endswith("pytest.py") for path in intake_result.source_paths)


def test_input_intake_generates_runtime_config_and_distribution() -> None:
    intake_result = load_input_intake(PACKAGE_DIR)

    assert intake_result.status == ValidationStatus.AUTO_FIXED
    assert intake_result.runtime_config is not None
    assert intake_result.implementation_spec is not None
    assert intake_result.implementation_spec.target_framework == "streamlit"
    assert intake_result.runtime_config.service_slug == "question_quest"
    assert intake_result.runtime_config.target_framework == "streamlit"
    assert intake_result.runtime_config.content_output_filename == "question_quest_contents.json"
    assert (
        intake_result.runtime_config.normalized_source_path
        == "inputs/mock_planning_outputs/question_quest_v0"
    )
    assert intake_result.runtime_config.content_distribution.item_count_by_type == {
        "multiple_choice": 1,
        "question_improvement": 2,
    }
    assert all(not path.startswith("/tmp/") for path in intake_result.source_paths)
    assert intake_result.quality_judgement is not None


def test_input_intake_marks_chatbot_total_count_as_planning_review() -> None:
    intake_result = load_input_intake(CHATBOT_PACKAGE_DIR)

    assert intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW
    assert intake_result.runtime_config is not None
    assert intake_result.implementation_spec is not None
    assert intake_result.runtime_config.content_types_source == "data_schema.output.mode.allowed_values"
    assert intake_result.runtime_config.total_count_source == "derived_from_mode_allowed_values_count"
    assert intake_result.runtime_config.screens_source == "interface_spec.screen_labels"
    assert intake_result.runtime_config.api_endpoints_source == "interface_spec.http_method_lines"
    assert intake_result.runtime_config.service_slug == "question_coaching_chatbot"
    assert (
        intake_result.runtime_config.content_output_filename
        == "question_coaching_chatbot_contents.json"
    )
    assert intake_result.runtime_config.content_distribution.item_count_by_type == {
        "need_specificity": 1,
        "need_context": 1,
        "need_purpose": 1,
        "completed": 1,
    }
    assert intake_result.runtime_config.content_distribution.distribution_source == (
        "data_schema.output.mode.allowed_values"
    )
    assert intake_result.implementation_spec.service_name == "Question Coaching Chatbot"
    assert intake_result.implementation_spec.total_count == 4
    assert any(
        item.field_path == "content_spec.total_count"
        and "mode.allowed_values" in item.reason
        for item in intake_result.planning_review_items
    )


def test_planning_package_adapter_forwards_target_framework() -> None:
    package = load_planning_package(PACKAGE_DIR)
    package = package.model_copy(
        update={
            "service_meta": package.service_meta.model_copy(
                update={"target_framework": "react"}
            )
        }
    )

    spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)

    assert spec.target_framework == "react"


def test_input_intake_marks_planning_review_without_blocking(tmp_path: Path) -> None:
    package_dir = tmp_path / "review_service_v0"
    shutil.copytree(PACKAGE_DIR, package_dir)
    (package_dir / "prompt_spec.md").write_text("# Prompt Spec\n\n## Empty\n", encoding="utf-8")

    intake_result = load_input_intake(package_dir)

    assert intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW
    assert any(
        item.field_path == "llm_spec.generation_prompt"
        for item in intake_result.planning_review_items
    )
    assert intake_result.implementation_spec is not None


def test_input_intake_missing_required_file_returns_fail(tmp_path: Path) -> None:
    package_dir = tmp_path / "missing_file_v0"
    shutil.copytree(PACKAGE_DIR, package_dir)
    (package_dir / "data_schema.json").unlink()

    intake_result = load_input_intake(package_dir)

    assert intake_result.status == ValidationStatus.FAIL
    assert intake_result.issues[0].code == "PLANNING_PACKAGE_FILE_MISSING"


def test_main_writes_input_intake_report_on_fail(tmp_path: Path) -> None:
    package_dir = tmp_path / "bad_json_service_v0"
    output_dir = tmp_path / "outputs"
    shutil.copytree(PACKAGE_DIR, package_dir)
    (package_dir / "data_schema.json").write_text("{not-json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "main.py"),
            "--input-package",
            str(package_dir),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    report_path = output_dir / "input_intake_report.json"
    assert result.returncode == 1
    assert "[FAILED] Input Intake Layer" in result.stdout
    assert report_path.exists()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["issues"][0]["code"] == "PLANNING_PACKAGE_PARSE_FAILED"


def test_main_warns_and_continues_on_planning_review(monkeypatch, capsys) -> None:
    intake_result = load_input_intake(CHATBOT_PACKAGE_DIR)
    assert intake_result.status == ValidationStatus.NEEDS_PLANNING_REVIEW
    assert intake_result.implementation_spec is not None

    called = {"ran": False}

    class DummyPipeline:
        def __init__(self, **kwargs):
            assert kwargs["implementation_spec"] == intake_result.implementation_spec
            assert kwargs["input_intake_result"] == intake_result

        def run(self):
            called["ran"] = True
            return {}

    class DummyClient:
        @classmethod
        def from_env(cls):
            return cls()

    monkeypatch.setattr(main_module, "load_input_intake", lambda _: intake_result)
    monkeypatch.setattr(main_module, "ImplementationPipeline", DummyPipeline)
    monkeypatch.setattr(main_module, "OpenAICompatibleClient", DummyClient)
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--input-package", str(CHATBOT_PACKAGE_DIR), "--output-dir", "tmp_outputs"],
    )

    result = main_module.main()

    captured = capsys.readouterr()
    assert result == 0
    assert called["ran"] is True
    assert "warn-and-continue policy" in captured.out
    assert "planning_review_items:" in captured.out
    assert "REVIEW content_spec.total_count" in captured.out


def test_parser_accepts_input_package_option() -> None:
    parser = build_parser()
    args = parser.parse_args(["--input-package", "inputs/mock_planning_outputs/question_quest_v0/"])

    assert args.input_package == "inputs/mock_planning_outputs/question_quest_v0/"


def test_pipeline_runs_with_planning_package_adapter(tmp_path: Path) -> None:
    intake_result = load_input_intake(PACKAGE_DIR)
    assert intake_result.implementation_spec is not None
    implementation_spec = intake_result.implementation_spec
    content_filename = build_content_filename(implementation_spec.service_name)

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=PACKAGE_DIR,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        implementation_spec=implementation_spec,
        input_intake_result=intake_result,
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    assert implementation_spec.total_count == 3
    assert implementation_spec.items_per_type == 2
    assert (tmp_path / "outputs" / "input_intake_report.json").exists()
    assert (tmp_path / "outputs" / content_filename).exists()
    assert (tmp_path / "app.py").exists()


def test_missing_package_dir_raises_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        load_planning_package(REPO_ROOT / "inputs" / "mock_planning_outputs" / "missing_package")
