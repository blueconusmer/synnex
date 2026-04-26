from __future__ import annotations

import json
from pathlib import Path

from orchestrator.pipeline import ImplementationPipeline
from schemas.implementation.implementation_spec import parse_markdown_spec
from tests.fakes import FakeLLMClient


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_parse_markdown_spec_extracts_expected_fields() -> None:
    spec = parse_markdown_spec(REPO_ROOT / "inputs" / "quiz_service_spec.md")

    assert spec.service_name == "질문력 향상 퀴즈 서비스 구현 명세서"
    assert "중학생" in spec.target_users
    assert len(spec.learning_goals) == 3
    assert any("총 8문제" in criterion for criterion in spec.acceptance_criteria)


def test_pipeline_with_fake_llm_generates_expected_outputs(tmp_path: Path) -> None:
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
        "quiz_contents.json",
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

    quiz_contents = json.loads((output_dir / "quiz_contents.json").read_text(encoding="utf-8"))
    assert len(quiz_contents["quiz_types"]) == 4
    assert len(quiz_contents["items"]) == 8
    assert set(quiz_contents["quiz_types"]) == {
        "더 좋은 질문 고르기",
        "질문에서 빠진 요소 찾기",
        "모호한 질문 고치기",
        "상황에 맞는 질문 만들기",
    }
    assert all("learning_dimension" in item for item in quiz_contents["items"])
    assert (tmp_path / "app.py").exists()
