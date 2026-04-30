from __future__ import annotations

import json
from pathlib import Path

from schemas.implementation.common import AgentLabel, SchemaModel


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_prompt_text(file_name: str) -> str:
    prompt_path = repo_root() / "prompts" / "implementation" / file_name
    return prompt_path.read_text(encoding="utf-8")


def dump_model(model: SchemaModel) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)


def dump_optional_model(model: SchemaModel | None, *, default: str = "없음") -> str:
    if model is None:
        return default
    return dump_model(model)


def make_label(english_name: str, korean_name: str) -> AgentLabel:
    return AgentLabel(english_name=english_name, korean_name=korean_name)
