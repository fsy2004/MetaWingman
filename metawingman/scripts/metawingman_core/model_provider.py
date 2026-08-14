"""Provider-neutral contracts for optional external model runtimes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol, Sequence, runtime_checkable


class ProviderRequestError(RuntimeError):
    """Raised when an external model-provider request is invalid or fails."""


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str
    finish_reason: str
    content: str
    content_sha256: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    reasoning_tokens: int | None
    system_fingerprint: str | None
    credential_source: str

    def audit_record(self, include_content: bool = False) -> dict[str, Any]:
        record = asdict(self)
        if not include_content:
            record.pop("content")
        return record


@runtime_checkable
class ModelProvider(Protocol):
    """Minimum capability required by MetaWingman model-driven modules."""

    credential_source: str

    def list_models(self) -> list[str]: ...

    def chat(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        model: str | None = None,
        thinking: bool = False,
        reasoning_effort: str = "low",
        max_tokens: int = 128,
        json_output: bool = False,
    ) -> ProviderResult: ...
