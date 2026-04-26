from __future__ import annotations

import json
import os
import re
import urllib.error
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


class OpenAICompatibleClient:
    """Minimal OpenAI-compatible JSON client for runtime execution."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 1,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

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

    def generate_json(
        self,
        *,
        prompt: str,
        response_model: type[ModelT],
        system_prompt: str | None = None,
    ) -> ModelT:
        schema = response_model.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": system_prompt
                or "You are a structured JSON generator. Return valid JSON only.",
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\n"
                    "Return only JSON that matches this schema:\n"
                    f"{json.dumps(schema, ensure_ascii=False, indent=2)}"
                ),
            },
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            content = ""
            try:
                response_payload = self._post_json(
                    url=f"{self.base_url}/chat/completions",
                    payload=payload,
                )
                content = (
                    response_payload["choices"][0]["message"]["content"]
                    if response_payload.get("choices")
                    else ""
                )
                data = self._extract_json(content)
                return response_model.model_validate(data)
            except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    payload["messages"].append(
                        {
                            "role": "assistant",
                            "content": content or "{}",
                        }
                    )
                    payload["messages"].append(
                        {
                            "role": "user",
                            "content": self._build_retry_instruction(
                                response_model_name=response_model.__name__,
                                error=exc,
                            ),
                        }
                    )
            except urllib.error.URLError as exc:
                last_error = exc

        raise RuntimeError(
            f"Failed to generate valid {response_model.__name__} output."
        ) from last_error

    def _post_json(self, *, url: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            url=url,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
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
