"""Provider-neutral adapter for bounded OpenAI-compatible chat endpoints."""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Sequence

from .model_provider import ProviderRequestError, ProviderResult
from .provider_secrets import ProviderSecretError, resolve_provider_secret


ALLOWED_ROLES = {"system", "user", "assistant", "tool"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class OpenAICompatibleProvider:
    """Call a configured chat-completions endpoint without vendor assumptions."""

    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str,
        model: str,
        api_key: str | None = None,
        api_key_required: bool = True,
        api_key_env: str = "MODEL_API_KEY",
        credential_target: str | None = None,
        allow_local_http: bool = False,
        supports_json_output: bool = True,
        supports_reasoning_effort: bool = False,
        timeout_seconds: float = 90.0,
        credential_source: str | None = None,
    ):
        if not provider_name.strip() or not model.strip():
            raise ProviderRequestError("provider_name and model are required")
        if api_key is None and api_key_required:
            try:
                api_key, resolved_source = resolve_provider_secret(api_key_env, credential_target)
            except ProviderSecretError as exc:
                raise ProviderRequestError(str(exc)) from exc
            credential_source = resolved_source
        if api_key_required and not (api_key or "").strip():
            raise ProviderRequestError("provider API key is empty")
        self.provider_name = provider_name.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model.strip()
        self._api_key = (api_key or "").strip()
        self.allow_local_http = allow_local_http
        self.supports_json_output = supports_json_output
        self.supports_reasoning_effort = supports_reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.credential_source = credential_source or "explicit_argument"
        self._validate_base_url()

    def _validate_base_url(self) -> None:
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme == "https" and parsed.hostname:
            return
        if (
            parsed.scheme == "http"
            and self.allow_local_http
            and parsed.hostname in LOOPBACK_HOSTS
        ):
            return
        raise ProviderRequestError(
            "provider base URL must use HTTPS; explicit local HTTP is limited to loopback"
        )

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MetaWingman/OpenAI-compatible-adapter-1.0",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderRequestError(
                f"{self.provider_name} HTTP {exc.code}: request rejected"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderRequestError(
                f"{self.provider_name} request failed: {type(exc).__name__}"
            ) from exc
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ProviderRequestError(
                f"{self.provider_name} returned invalid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise ProviderRequestError(f"{self.provider_name} returned a non-object response")
        return parsed

    def list_models(self) -> list[str]:
        response = self._request("GET", "/models")
        models = response.get("data")
        if not isinstance(models, list):
            raise ProviderRequestError("model-list response is malformed")
        return sorted(
            item["id"]
            for item in models
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
        normalized: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if role not in ALLOWED_ROLES or not isinstance(content, str) or not content:
                raise ProviderRequestError(
                    "messages require a supported role and non-empty text content"
                )
            normalized.append({"role": role, "content": content})
        if reasoning_effort not in {"low", "high", "max"}:
            raise ProviderRequestError("reasoning_effort must be low, high, or max")
        if not 1 <= max_tokens <= 8192:
            raise ProviderRequestError("max_tokens must be between 1 and 8192")
        if json_output and not self.supports_json_output:
            raise ProviderRequestError("configured provider does not support JSON output mode")
        if thinking and not self.supports_reasoning_effort:
            raise ProviderRequestError("configured provider does not support reasoning effort")
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": normalized,
            "stream": False,
            "max_tokens": max_tokens,
        }
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        if thinking:
            payload["reasoning_effort"] = reasoning_effort
        response = self._request("POST", "/chat/completions", payload)
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderRequestError("completion response has no choices")
        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderRequestError("completion content is missing")
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        details = usage.get("completion_tokens_details")
        details = details if isinstance(details, dict) else {}
        return ProviderResult(
            provider=self.provider_name,
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
