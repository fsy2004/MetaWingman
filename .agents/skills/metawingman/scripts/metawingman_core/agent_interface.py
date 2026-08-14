"""Bounded action and observation interface with control/data separation."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal

from .action_guard import ActionDecision, evaluate_action
from .schema_guard import SchemaValidationError, load_schema, validate_document
from .state_store import sha256_json


AgentTurnStatus = Literal["allowed", "blocked", "abstained"]
MAX_OBSERVATION_BYTES = 100_000

# Pattern matching is only a diagnostic layer. Authorization is prevented by the
# typed control/data split even when a novel injection pattern is not detected.
INJECTION_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|override|forget)\b.{0,80}\b(previous|prior|system|developer|instruction|rule)",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "authority_impersonation",
        re.compile(r"\b(system|developer|administrator)\s*(message|instruction|prompt)\s*:", re.IGNORECASE),
    ),
    (
        "tool_execution_request",
        re.compile(
            r"\b(run|execute|invoke|call|launch|open)\b.{0,60}\b(shell|powershell|cmd|terminal|tool|browser|script|command)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "credential_request",
        re.compile(r"\b(api[ _-]?key|password|secret|access[ _-]?token|credential|cookie)\b", re.IGNORECASE),
    ),
    (
        "exfiltration_request",
        re.compile(
            r"\b(upload|send|post|transmit|exfiltrat\w*)\b.{0,80}\b(file|data|document|record|secret|credential)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "hidden_instruction_markup",
        re.compile(r"<!--.{0,400}(ignore|instruction|execute|system prompt).{0,400}-->", re.IGNORECASE | re.DOTALL),
    ),
    (
        "prompt_disclosure_request",
        re.compile(r"\b(reveal|print|show|return)\b.{0,80}\b(system|developer)\s+prompt\b", re.IGNORECASE | re.DOTALL),
    ),
)


class AgentInterfaceError(ValueError):
    """Raised when an agent turn violates the bounded interface."""


@dataclass(frozen=True)
class AgentTurnDecision:
    status: AgentTurnStatus
    reason_codes: tuple[str, ...]
    required_human_role: str

    @property
    def allowed(self) -> bool:
        return self.status == "allowed"


def _normalized_security_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return "".join(character for character in normalized if character in "\n\t" or unicodedata.category(character) != "Cf")


def detect_instruction_signals(text: str) -> tuple[str, ...]:
    normalized = _normalized_security_text(text)
    return tuple(code for code, pattern in INJECTION_SIGNALS if pattern.search(normalized))


def build_observation(
    *,
    observation_id: str,
    task_id: str,
    content: str | bytes,
    source_type: str,
    tool: str,
    tool_version: str,
    uri: str | None = None,
    media_type: str = "text/plain",
    excerpts: Iterable[dict[str, Any]] = (),
    facts: Iterable[dict[str, Any]] = (),
    max_bytes: int = MAX_OBSERVATION_BYTES,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    raw = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    if max_bytes < 0:
        raise AgentInterfaceError("max_bytes must be non-negative")
    included = raw[:max_bytes]
    text = included.decode("utf-8", errors="replace")
    signals = detect_instruction_signals(text)
    if source_type in {"system_state", "frozen_protocol"}:
        trust = "trusted_control"
    elif source_type == "user_artifact":
        trust = "trusted_data"
    else:
        trust = "untrusted_data"
    observation = {
        "schema_version": "1.0",
        "observation_id": observation_id,
        "task_id": task_id,
        "source": {
            "type": source_type,
            "trust": trust,
            "uri": uri,
            "tool": tool,
            "tool_version": tool_version,
        },
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "media_type": media_type,
        "excerpts": list(excerpts),
        "facts": list(facts),
        "security": {
            "instruction_like_content_detected": bool(signals),
            "signal_codes": list(signals),
            "quarantined": bool(signals),
            "allowed_interpretation": "evidence_data_only",
        },
        "truncation": {
            "original_bytes": len(raw),
            "included_bytes": len(included),
            "strategy": "none" if len(included) == len(raw) else "head",
        },
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
    }
    try:
        validate_document(observation, "agent_observation")
    except SchemaValidationError as exc:
        raise AgentInterfaceError(str(exc)) from exc
    return observation


def observation_binding_sha256(
    task_id: str,
    control_refs: Iterable[dict[str, Any]],
    observations: Iterable[dict[str, Any]],
) -> str:
    controls = sorted(
        (
            {
                "control_id": item["control_id"],
                "source": item["source"],
                "sha256": item["sha256"],
            }
            for item in control_refs
        ),
        key=lambda item: (item["source"], item["control_id"]),
    )
    observed = sorted(
        (
            {
                "observation_id": item["observation_id"],
                "content_sha256": item["content_sha256"],
            }
            for item in observations
        ),
        key=lambda item: item["observation_id"],
    )
    return sha256_json({"task_id": task_id, "control_refs": controls, "observations": observed})


def detect_fact_conflicts(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, dict[str, set[str]]] = {}
    for observation in observations:
        for fact in observation["facts"]:
            field = fact["field"]
            encoded = sha256_json(fact["value"])
            values.setdefault(field, {}).setdefault(encoded, set()).add(observation["observation_id"])
    conflicts: list[dict[str, Any]] = []
    for field, variants in sorted(values.items()):
        if len(variants) < 2:
            continue
        conflicts.append({
            "field": field,
            "variant_count": len(variants),
            "observation_ids": sorted({identifier for identifiers in variants.values() for identifier in identifiers}),
        })
    return conflicts


class BoundedAgentInterface:
    """Validate one agent turn without exposing an unrestricted shell or browser."""

    def __init__(
        self,
        *,
        allowed_tool_contract_ids: Iterable[str],
        allowed_output_schemas: Iterable[str],
        trusted_control_refs: Iterable[dict[str, str]],
    ):
        self.allowed_tool_contract_ids = frozenset(allowed_tool_contract_ids)
        self.allowed_output_schemas = frozenset(allowed_output_schemas)
        self.trusted_control_refs = {
            (item["source"], item["control_id"]): item["sha256"]
            for item in trusted_control_refs
        }

    def authorize(
        self,
        envelope: dict[str, Any],
        observations: Iterable[dict[str, Any]],
        project_root: Any = None,
    ) -> AgentTurnDecision:
        try:
            validate_document(envelope, "agent_action_envelope")
            validate_document(envelope["action"], "scientific_action")
            observation_list = list(observations)
            for observation in observation_list:
                validate_document(observation, "agent_observation")
        except (SchemaValidationError, TypeError) as exc:
            return AgentTurnDecision("blocked", ("schema_validation_failed", str(exc)), "runtime_operator")

        if envelope["attempt"] > envelope["max_attempts"]:
            return AgentTurnDecision("blocked", ("attempt_budget_exceeded",), "runtime_operator")
        if envelope["tool_contract_id"] not in self.allowed_tool_contract_ids:
            return AgentTurnDecision("blocked", ("tool_contract_not_allowed",), "runtime_operator")
        if envelope["expected_output_schema"] not in self.allowed_output_schemas:
            return AgentTurnDecision("blocked", ("output_schema_not_allowed",), "runtime_operator")
        try:
            load_schema(envelope["expected_output_schema"])
        except FileNotFoundError:
            return AgentTurnDecision("blocked", ("output_schema_missing",), "runtime_operator")

        for control in envelope["control_refs"]:
            registered_hash = self.trusted_control_refs.get(
                (control["source"], control["control_id"])
            )
            if registered_hash != control["sha256"]:
                return AgentTurnDecision("blocked", ("unregistered_control_ref",), "runtime_operator")

        by_id = {item["observation_id"]: item for item in observation_list}
        if len(by_id) != len(observation_list):
            return AgentTurnDecision("blocked", ("duplicate_observation_id",), "runtime_operator")
        requested_ids = envelope["observation_ids"]
        if set(requested_ids) != set(by_id):
            return AgentTurnDecision("blocked", ("observation_set_mismatch",), "runtime_operator")
        if any(item["task_id"] != envelope["task_id"] for item in observation_list):
            return AgentTurnDecision("blocked", ("cross_task_observation",), "runtime_operator")

        action = envelope["action"]
        expected_hash = observation_binding_sha256(
            envelope["task_id"], envelope["control_refs"], observation_list
        )
        if action["input_sha256"] != expected_hash:
            return AgentTurnDecision("blocked", ("observation_binding_hash_mismatch",), "runtime_operator")

        if action["human_approval"]["status"] == "approved":
            approval_id = f"approval:{action['action_id']}"
            expected_approval_hash = sha256_json(action["human_approval"])
            if not any(
                item["source"] == "user"
                and item["control_id"] == approval_id
                and item["sha256"] == expected_approval_hash
                for item in envelope["control_refs"]
            ):
                return AgentTurnDecision(
                    "blocked", ("trusted_human_approval_control_missing",), "human_lead"
                )

        conflicts = detect_fact_conflicts(observation_list)
        if conflicts and action["action_type"] in {
            "finalize_exclusion", "propose_extraction", "run_analysis", "draft_claim",
            "finalize_risk_of_bias", "finalize_grade", "decide_poolability",
        }:
            return AgentTurnDecision(
                "abstained",
                ("poisoned_or_conflicting_retrieval", *(f"conflict:{item['field']}" for item in conflicts)),
                "domain_reviewer",
            )

        action_decision: ActionDecision = evaluate_action(action, project_root)
        return AgentTurnDecision(
            action_decision.status,
            action_decision.reason_codes,
            action_decision.required_human_role,
        )
