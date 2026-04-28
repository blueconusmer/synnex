from __future__ import annotations

import ast
import json
import subprocess
import sys
import time
from pathlib import Path

from agents.implementation.prototype_builder_agent import run_prototype_builder_agent
from loaders import load_planning_package, planning_package_to_implementation_spec
from orchestrator.app_source import build_content_filename, build_streamlit_app_source
from schemas.implementation.content_interaction import ContentInteractionOutput
from schemas.implementation.prototype_builder import PrototypeBuilderInput
from schemas.implementation.requirement_mapping import RequirementMappingOutput
from schemas.implementation.spec_intake import SpecIntakeOutput
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def _assert_streamlit_app_starts(app_path: Path, *, cwd: Path, port: int) -> None:
    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(app_path)],
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
        ],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)
    assert process.poll() is None
    process.terminate()
    output = process.communicate(timeout=5)[0]
    assert "Traceback" not in output


def _build_package_content_output() -> tuple[str, ContentInteractionOutput]:
    fake = FakeLLMClient()
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    package = load_planning_package(package_dir)
    implementation_spec = planning_package_to_implementation_spec(package, package_dir)
    content_filename = build_content_filename(implementation_spec.service_name)
    content_output = fake.generate_json(
        prompt="\n".join(
            [
                f"- service_name: {implementation_spec.service_name}",
                '- content_types: ["multiple_choice", "question_improvement"]',
                '- learning_goals: ["구체성", "맥락성", "목적성"]',
                "- total_count: 3",
                "- items_per_type: 2",
            ]
        ),
        response_model=ContentInteractionOutput,
    )
    return content_filename, content_output


def test_generated_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    content_filename = build_content_filename("질문력 향상 퀴즈 서비스")

    quiz_contents = FakeLLMClient().generate_json(
        prompt="",
        response_model=ContentInteractionOutput,
    )
    (output_dir / content_filename).write_text(
        json.dumps(quiz_contents.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app_path.write_text(
        build_streamlit_app_source("질문력 향상 퀴즈 서비스", content_filename),
        encoding="utf-8",
    )
    source = app_path.read_text(encoding="utf-8")
    assert "CONTENT_CANDIDATE_PATHS" in source
    assert "FALLBACK_OUTPUT_PATH" in source

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8766)


def test_generated_quest_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    fake = FakeLLMClient()
    package_dir = REPO_ROOT / "inputs" / "mock_planning_outputs" / "question_quest_v0"
    package = load_planning_package(package_dir)
    implementation_spec = planning_package_to_implementation_spec(package, package_dir)
    content_filename, content_output = _build_package_content_output()

    (output_dir / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    builder_output = run_prototype_builder_agent(
        PrototypeBuilderInput(
            spec_intake_output=fake.generate_json(prompt="", response_model=SpecIntakeOutput),
            requirement_mapping_output=fake.generate_json(
                prompt="",
                response_model=RequirementMappingOutput,
            ),
            content_interaction_output=content_output,
            implementation_spec=implementation_spec,
        ),
        fake,
    )
    app_path.write_text(builder_output.generated_files[0].content, encoding="utf-8")
    source = app_path.read_text(encoding="utf-8")
    assert "CONTENT_CANDIDATE_PATHS" in source
    assert "FALLBACK_OUTPUT_PATH" in source
    assert "load_planning_package" not in source

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8767)


def test_root_app_reads_outputs_content_file(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    content_filename, content_output = _build_package_content_output()
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    (output_dir / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8768)


def test_root_app_reads_root_fallback_content_file(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    content_filename, content_output = _build_package_content_output()
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / content_filename).write_text(
        json.dumps(content_output.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _assert_streamlit_app_starts(app_path, cwd=tmp_path, port=8769)


def test_root_app_starts_without_content_file_and_shows_warning(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text((REPO_ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")

    compile_result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(app_path)],
        capture_output=True,
        text=True,
    )
    assert compile_result.returncode == 0, compile_result.stderr

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
            "--server.port",
            "8770",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(3)
    assert process.poll() is None
    process.terminate()
    output = process.communicate(timeout=5)[0]
    assert "Traceback" not in output


def test_root_app_improvement_evaluator_call_arity_matches_definition() -> None:
    source = (REPO_ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "evaluate_improvement_question"
    ]
    assert definitions, "evaluate_improvement_question definition is missing"

    definition = definitions[0]
    positional_args = [*definition.args.posonlyargs, *definition.args.args]
    max_positional_args = len(positional_args)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "evaluate_improvement_question":
            continue
        assert len(node.args) <= max_positional_args
