from __future__ import annotations

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
            "8766",
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


def test_generated_quest_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

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
            "8767",
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
