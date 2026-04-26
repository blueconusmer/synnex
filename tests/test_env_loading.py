from __future__ import annotations

import os
from pathlib import Path

from clients.env import load_env_file


def test_load_env_file_reads_simple_key_values(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'UPSTAGE_API_KEY="sample-key"\nUPSTAGE_MODEL=solar-pro2\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)
    monkeypatch.delenv("UPSTAGE_MODEL", raising=False)

    load_env_file(env_path)

    assert os.environ["UPSTAGE_API_KEY"] == "sample-key"
    assert os.environ["UPSTAGE_MODEL"] == "solar-pro2"


def test_load_env_file_does_not_override_existing_env(tmp_path: Path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("UPSTAGE_MODEL=solar-pro2\n", encoding="utf-8")
    monkeypatch.setenv("UPSTAGE_MODEL", "existing-model")

    load_env_file(env_path)

    assert os.environ["UPSTAGE_MODEL"] == "existing-model"
