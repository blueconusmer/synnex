from __future__ import annotations

from clients.llm import FallbackLLMClient, OpenAICompatibleClient


def test_fallback_client_prefers_gemini_then_upstage(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.1-pro")
    monkeypatch.setenv("UPSTAGE_API_KEY", "upstage-key")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-pro2")

    client = FallbackLLMClient.from_env()

    assert client.provider_names == ["gemini", "upstage"]
    assert client.providers[0].model == "gemini-3.1-pro-preview"
    assert client.providers[1].model == "solar-pro2"


def test_fallback_client_uses_defaults_for_gemini_and_upstage(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.setenv("UPSTAGE_API_KEY", "upstage-key")
    monkeypatch.delenv("UPSTAGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    client = FallbackLLMClient.from_env()

    assert client.provider_names == ["gemini", "upstage"]
    assert client.providers[0].model == "gemini-3.1-pro-preview"
    assert client.providers[1].model == "solar-pro2"


def test_fallback_client_requires_gemini_or_upstage(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    try:
        FallbackLLMClient.from_env()
        assert False, "Expected provider configuration error"
    except RuntimeError as exc:
        assert "GEMINI_API_KEY or UPSTAGE_API_KEY" in str(exc)


def test_openai_compatible_client_from_env_prefers_upstage_settings(monkeypatch) -> None:
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-pro2")
    monkeypatch.setenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_MODEL", "ignored-model")

    client = OpenAICompatibleClient.from_env()

    assert client.api_key == "test-upstage-key"
    assert client.model == "solar-pro2"
    assert client.base_url == "https://api.upstage.ai/v1"
