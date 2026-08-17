"""Minimal OpenAI-compatible DeepSeek provider adapter with secret-safe telemetry."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from typing import Any, Sequence

from .provider_secrets import (
    DEEPSEEK_CREDENTIAL_TARGET,
    ProviderSecretError,
    resolve_provider_secret,
)
from .model_provider import ProviderRequestError, ProviderResult


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


class DeepSeekProvider:
    """Call the official DeepSeek chat-completions endpoint using a bounded interface."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 90.0,
        credential_source: str | None = None,
    ):
        if api_key is None:
            try:
                api_key, resolved_source = resolve_provider_secret(
                    "DEEPSEEK_API_KEY", DEEPSEEK_CREDENTIAL_TARGET
                )
            except ProviderSecretError as exc:
                raise ProviderRequestError(str(exc)) from exc
            credential_source = resolved_source
        if not api_key.strip():
            raise ProviderRequestError("DeepSeek API key is empty")
        self._api_key = api_key
        self.base_url = (base_url or os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("DEEPSEEK_MODEL") or DEFAULT_MODEL
        self.timeout_seconds = timeout_seconds
        self.credential_source = credential_source or "explicit_argument"
        if not self.base_url.startswith("https://"):
            raise ProviderRequestError("DeepSeek base URL must use HTTPS")

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "MetaWingman/DeepSeek-adapter-1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read(4096).decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                message = parsed.get("error", {}).get("message") or parsed.get("message")
            except json.JSONDecodeError:
                message = None
            raise ProviderRequestError(
                f"DeepSeek HTTP {exc.code}: {message or 'request rejected'}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderRequestError(f"DeepSeek request failed: {type(exc).__name__}") from exc
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ProviderRequestError("DeepSeek returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ProviderRequestError("DeepSeek returned a non-object response")
        return parsed

    def list_models(self) -> list[str]:
        response = self._request("GET", "/models")
        models = response.get("data")
        if not isinstance(models, list):
            raise ProviderRequestError("DeepSeek model-list response is malformed")
        return sorted(
            item["id"] for item in models
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        )

    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        model: str | None = None,
        thinking: bool = False,
        reasoning_effort: str = "low",
        max_tokens: int = 128,
        json_output: bool = False,
    ) -> ProviderResult:
        if not messages:
            raise ProviderRequestError("at least one message is required")
        normalized: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in ALLOWED_ROLES or not isinstance(content, str) or not content:
                raise ProviderRequestError("messages require a supported role and non-empty text content")
            normalized.append({"role": role, "content": content})
        if reasoning_effort not in {"low", "high", "max"}:
            raise ProviderRequestError("reasoning_effort must be low, high, or max")
        if max_tokens < 1 or max_tokens > 8192:
            raise ProviderRequestError("max_tokens must be between 1 and 8192")
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": normalized,
            "stream": False,
            "max_tokens": max_tokens,
            "thinking": {
                "type": "enabled" if thinking else "disabled",
                "reasoning_effort": reasoning_effort,
            },
        }
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        response = self._request("POST", "/chat/completions", payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderRequestError("DeepSeek completion response has no choices")
        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderRequestError("DeepSeek completion content is missing")
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        return ProviderResult(
            provider="deepseek",
            model=str(response.get("model") or payload["model"]),
            finish_reason=str(first.get("finish_reason") or "unknown"),
            content=content,
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            reasoning_tokens=details.get("reasoning_tokens"),
            system_fingerprint=response.get("system_fingerprint"),
            credential_source=self.credential_source,
        )
