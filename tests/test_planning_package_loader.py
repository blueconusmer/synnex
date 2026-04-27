from __future__ import annotations

from pathlib import Path

import pytest

from loaders import load_planning_package, planning_package_to_implementation_spec
from main import build_parser
from orchestrator.app_source import build_content_filename
from orchestrator.pipeline import ImplementationPipeline
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"


def test_load_planning_package_reads_fixture_files() -> None:
    package = load_planning_package(PACKAGE_DIR)

    assert package.service_meta.service_name == "question_quest"
    assert package.service_meta.version == "v0"
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


def test_loader_falls_back_on_parse_failures(tmp_path: Path) -> None:
    package_dir = tmp_path / "example_service_v1"
    package_dir.mkdir()
    (package_dir / "constitution.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "data_schema.json").write_text("{not-json", encoding="utf-8")
    (package_dir / "state_machine.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "prompt_spec.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "interface_spec.md").write_text("# Empty\n", encoding="utf-8")
    (package_dir / "pytest.py").write_text('"""\nplaceholder\n"""', encoding="utf-8")

    package = load_planning_package(package_dir)

    assert package.service_meta.service_name == "example_service"
    assert package.service_meta.version == "v1"
    assert package.content_spec.content_types == []
    assert package.content_spec.total_count == 0
    assert package.interface_spec.screens == []
    assert package.llm_spec.generation_prompt == ""
    assert package.test_spec.acceptance_criteria == []


def test_parser_accepts_input_package_option() -> None:
    parser = build_parser()
    args = parser.parse_args(["--input-package", "inputs/mock_planning_outputs/question_quest_v0/"])

    assert args.input_package == "inputs/mock_planning_outputs/question_quest_v0/"


def test_pipeline_runs_with_planning_package_adapter(tmp_path: Path) -> None:
    package = load_planning_package(PACKAGE_DIR)
    implementation_spec = planning_package_to_implementation_spec(package, PACKAGE_DIR)
    content_filename = build_content_filename(implementation_spec.service_name)

    pipeline = ImplementationPipeline(
        llm_client=FakeLLMClient(),
        spec_path=PACKAGE_DIR,
        workspace_dir=tmp_path,
        output_dir=tmp_path / "outputs",
        implementation_spec=implementation_spec,
        app_target_path=tmp_path / "app.py",
        enable_streamlit_smoke=False,
    )

    pipeline.run()

    assert implementation_spec.total_count == 3
    assert implementation_spec.items_per_type == 2
    assert (tmp_path / "outputs" / content_filename).exists()
    assert (tmp_path / "app.py").exists()


def test_missing_package_dir_raises_file_not_found_error() -> None:
    with pytest.raises(FileNotFoundError):
        load_planning_package(REPO_ROOT / "inputs" / "mock_planning_outputs" / "missing_package")
