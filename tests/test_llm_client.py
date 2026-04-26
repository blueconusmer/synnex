from __future__ import annotations

from clients.llm import OpenAICompatibleClient


def test_from_env_prefers_upstage_settings(monkeypatch) -> None:
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-pro2")
    monkeypatch.setenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "ignored-model")

    client = OpenAICompatibleClient.from_env()

    assert client.api_key == "test-upstage-key"
    assert client.model == "solar-pro2"
    assert client.base_url == "https://api.upstage.ai/v1"


def test_from_env_uses_upstage_defaults(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.delenv("UPSTAGE_MODEL", raising=False)
    monkeypatch.delenv("UPSTAGE_BASE_URL", raising=False)

    client = OpenAICompatibleClient.from_env()

    assert client.api_key == "test-upstage-key"
    assert client.model == "solar-pro2"
    assert client.base_url == "https://api.upstage.ai/v1"
