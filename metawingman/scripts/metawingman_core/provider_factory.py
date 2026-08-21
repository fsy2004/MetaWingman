"""Construct external model providers from secret-free validated configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .deepseek_provider import DeepSeekProvider
from .model_provider import ModelProvider, ProviderRequestError
from .openai_compatible_provider import OpenAICompatibleProvider
from .provider_secrets import ProviderSecretError, resolve_provider_secret
from .schema_guard import SchemaValidationError, validate_document


def load_provider_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        validate_document(config, "provider_config")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise ProviderRequestError(f"invalid provider configuration: {exc}") from exc
    return config


def build_provider(config: dict[str, Any]) -> ModelProvider:
    try:
        validate_document(config, "provider_config")
        if config["api_key_required"]:
            api_key, credential_source = resolve_provider_secret(
                config["api_key_env"], config["credential_target"]
            )
        else:
            api_key, credential_source = "", "none"
    except (SchemaValidationError, ProviderSecretError) as exc:
        raise ProviderRequestError(str(exc)) from exc
    if config["adapter"] == "deepseek":
        if not config["features"]["deepseek_thinking"]:
            raise ProviderRequestError("deepseek adapter requires deepseek_thinking support")
        return DeepSeekProvider(
            api_key=api_key,
            base_url=config["base_url"],
            model=config["model"],
            credential_source=credential_source,
            timeout_seconds=float(config.get("timeout_seconds", 90.0)),
        )
    return OpenAICompatibleProvider(
        provider_name=config["display_name"],
        api_key=api_key,
        api_key_required=config["api_key_required"],
        base_url=config["base_url"],
        model=config["model"],
        allow_local_http=config["allow_local_http"],
        supports_json_output=config["features"]["json_output"],
        supports_reasoning_effort=config["features"]["reasoning_effort"],
        credential_source=credential_source,
        timeout_seconds=float(config.get("timeout_seconds", 90.0)),
    )
