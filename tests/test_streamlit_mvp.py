from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from orchestrator.app_source import build_streamlit_app_source
from schemas.implementation.content_interaction import ContentInteractionOutput
from tests.fakes import FakeLLMClient


def test_generated_streamlit_app_compiles_and_starts(tmp_path: Path) -> None:
    app_path = tmp_path / "app.py"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    quiz_contents = FakeLLMClient().generate_json(
        prompt="",
        response_model=ContentInteractionOutput,
    )
    (output_dir / "quiz_contents.json").write_text(
        json.dumps(quiz_contents.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    app_path.write_text(build_streamlit_app_source(), encoding="utf-8")

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
