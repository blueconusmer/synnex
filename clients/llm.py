from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol, TypeVar

from pydantic import ValidationError

from schemas.implementation.common import SchemaModel

ModelT = TypeVar("ModelT", bound=SchemaModel)


class LLMClient(Protocol):
    def generate_json(
        self,
        *,
        prompt: str,
        response_model: type[ModelT],
        system_prompt: str | None = None,
    ) -> ModelT:
        """Return a validated Pydantic model for the requested response."""


class ProviderConfigurationError(RuntimeError):
    """Raised when no configured provider is available."""


class BaseStructuredClient:
    """Shared JSON-validation loop for provider-specific LLM clients."""

    provider_name = "base"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def generate_json(
        self,
        *,
        prompt: str,
        response_model: type[ModelT],
        system_prompt: str | None = None,
    ) -> ModelT:
        schema = response_model.model_json_schema()
        full_prompt = (
            f"{prompt}\n\n"
            "Return only JSON that matches this schema:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
        )

        last_error: Exception | None = None
        previous_response = ""
        current_prompt = full_prompt
        for attempt in range(self.max_retries + 1):
            try:
                content = self._generate_content(
                    prompt=current_prompt,
                    system_prompt=system_prompt,
                )
                previous_response = content
                data = self._extract_json(content)
                return response_model.model_validate(data)
            except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    current_prompt = (
                        f"{full_prompt}\n\n"
                        f"Previous invalid response:\n{previous_response or '{}'}\n\n"
                        f"{self._build_retry_instruction(response_model_name=response_model.__name__, error=exc)}"
                    )
            except urllib.error.URLError as exc:
                last_error = exc
                break

        raise RuntimeError(
            f"{self.provider_name} failed to generate valid {response_model.__name__} output."
        ) from last_error

    def _generate_content(self, *, prompt: str, system_prompt: str | None = None) -> str:
        raise NotImplementedError

    def _post_json(
        self,
        *,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, object]:
        request = urllib.request.Request(
            url=url,
            method="POST",
            headers={
                "Content-Type": "application/json",
                **headers,
            },
            data=json.dumps(payload).encode("utf-8"),
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    @staticmethod
    def _extract_json(content: str) -> dict[str, object]:
        stripped = content.strip()
        if not stripped:
            raise json.JSONDecodeError("Empty content", doc=content, pos=0)

        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", stripped, re.DOTALL)
        if fenced_match:
            stripped = fenced_match.group(1)

        if not stripped.startswith("{"):
            json_match = re.search(r"(\{.*\})", stripped, re.DOTALL)
            if json_match:
                stripped = json_match.group(1)

        return json.loads(stripped)

    @staticmethod
    def _build_retry_instruction(*, response_model_name: str, error: Exception) -> str:
        return (
            f"Your previous response did not validate as {response_model_name}.\n"
            f"Validation error summary: {error}\n\n"
            "Return one concrete JSON object instance with filled values only.\n"
            "Do not return a JSON Schema.\n"
            "Do not include keys like `$defs`, `properties`, `required`, `title`, `type`, or `additionalProperties`.\n"
            "Return JSON only."
        )


class OpenAICompatibleClient(BaseStructuredClient):
    """Minimal OpenAI-compatible JSON client for runtime execution."""

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.base_url = base_url.rstrip("/")

    @classmethod
    def from_env(cls) -> "OpenAICompatibleClient":
        if os.getenv("UPSTAGE_API_KEY"):
            api_key = os.getenv("UPSTAGE_API_KEY")
            model = os.getenv("UPSTAGE_MODEL") or os.getenv("OPENAI_MODEL") or "solar-pro2"
            base_url = os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
            return cls(api_key=api_key, model=model, base_url=base_url)

        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL")
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        if not api_key:
            raise RuntimeError("Neither UPSTAGE_API_KEY nor OPENAI_API_KEY is set.")
        if not model:
            raise RuntimeError("OPENAI_MODEL is not set.")

        return cls(api_key=api_key, model=model, base_url=base_url)

    def _generate_content(self, *, prompt: str, system_prompt: str | None = None) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                    or "You are a structured JSON generator. Return valid JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        response_payload = self._post_json(
            url=f"{self.base_url}/chat/completions",
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        if not response_payload.get("choices"):
            raise KeyError("OpenAI-compatible response is missing choices.")
        return response_payload["choices"][0]["message"]["content"]


class GeminiClient(BaseStructuredClient):
    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=_normalize_gemini_model(model),
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
        self.base_url = base_url.rstrip("/")

    def _generate_content(self, *, prompt: str, system_prompt: str | None = None) -> str:
        payload: dict[str, object] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {
                "parts": [{"text": system_prompt}],
            }

        encoded_model = urllib.parse.quote(self.model, safe="")
        response_payload = self._post_json(
            url=f"{self.base_url}/models/{encoded_model}:generateContent?key={urllib.parse.quote(self.api_key, safe='')}",
            payload=payload,
            headers={},
        )
        candidates = response_payload.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise KeyError("Gemini response is missing candidates.")
        candidate = candidates[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not isinstance(parts, list) or not parts:
            raise KeyError("Gemini response is missing content parts.")
        texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        joined = "\n".join(text for text in texts if text)
        if not joined:
            raise KeyError("Gemini response did not include text content.")
        return joined


class UpstageClient(OpenAICompatibleClient):
    provider_name = "upstage"


class FallbackLLMClient:
    """Provider-priority client with sequential failover."""

    def __init__(self, providers: list[BaseStructuredClient]) -> None:
        if not providers:
            raise ProviderConfigurationError("No LLM providers are configured.")
        self.providers = providers

    @property
    def provider_names(self) -> list[str]:
        return [provider.provider_name for provider in self.providers]

    @classmethod
    def from_env(cls) -> "FallbackLLMClient":
        providers: list[BaseStructuredClient] = []

        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            providers.append(
                GeminiClient(
                    api_key=gemini_key,
                    model=os.getenv("GEMINI_MODEL", "gemini-3.1-pro"),
                    base_url=os.getenv(
                        "GEMINI_BASE_URL",
                        "https://generativelanguage.googleapis.com/v1beta",
                    ),
                )
            )

        upstage_key = os.getenv("UPSTAGE_API_KEY")
        if upstage_key:
            providers.append(
                UpstageClient(
                    api_key=upstage_key,
                    model=os.getenv("UPSTAGE_MODEL") or os.getenv("OPENAI_MODEL") or "solar-pro2",
                    base_url=os.getenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1"),
                )
            )

        if not providers:
            raise ProviderConfigurationError(
                "No LLM provider is configured. Set GEMINI_API_KEY or UPSTAGE_API_KEY."
            )

        return cls(providers)

    def generate_json(
        self,
        *,
        prompt: str,
        response_model: type[ModelT],
        system_prompt: str | None = None,
    ) -> ModelT:
        errors: list[str] = []
        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return provider.generate_json(
                    prompt=prompt,
                    response_model=response_model,
                    system_prompt=system_prompt,
                )
            except Exception as exc:
                last_error = exc
                errors.append(f"{provider.provider_name}: {exc}")

        raise RuntimeError(
            "All configured LLM providers failed. " + " | ".join(errors)
        ) from last_error
def _normalize_gemini_model(model: str) -> str:
    normalized = model.strip()
    lowered = normalized.lower()
    alias_map = {
        "gemini 3.1 pro": "gemini-3.1-pro-preview",
        "gemini-3.1-pro": "gemini-3.1-pro-preview",
        "models/gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
    }
    if lowered in alias_map:
        return alias_map[lowered]
    if lowered.startswith("models/"):
        return normalized.split("/", 1)[1]
    return normalized
