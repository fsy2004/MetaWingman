"""Freeze, validate, execute, resume, and lock five-arm question-synthesis runs."""

from __future__ import annotations

import hashlib
import json
import random
import re
import time
import tracemalloc
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Callable

from .schema_guard import SchemaValidationError, validate_document


CONFIGURATION_IDS = (
    "general-model-baseline",
    "generic-retrieval",
    "biomedical-schema",
    "biomedical-routing",
    "full-biomedical-stack",
)
ORCHESTRATION_SEEDS = (20260820, 20260821, 20260822)
PROMPT_TEMPLATES = {
    "general-model-baseline": (
        "Generate one clinically answerable review-question candidate from clinical_context only. "
        "Return one JSON object. Do not infer hidden or sealed benchmark material."
    ),
    "generic-retrieval": (
        "Generate one clinically answerable review-question candidate using only clinical_context and "
        "retrieved_visible_material. For role=proposal return a complete candidate object; for role=opposition "
        "return a critique object; for role=judge return exactly one object containing a complete revised "
        "candidate under the candidate key. Return JSON only. Do not infer hidden or sealed benchmark material."
    ),
    "biomedical-schema": (
        "Generate one clinically answerable review-question candidate using only the declared visible inputs and "
        "satisfy required_output_schema. Return one JSON object. Do not infer hidden or sealed benchmark material."
    ),
    "biomedical-routing": (
        "Jointly design the review question and synthesis method using only the declared visible inputs, "
        "required_output_schema, and executable_method_registry. Return one JSON object. Do not infer hidden or "
        "sealed benchmark material."
    ),
    "full-biomedical-stack": (
        "Jointly design the review question and executable synthesis method from only the declared visible inputs. "
        "For role=proposal return a candidate object; for role=opposition return a critique object; for role=judge "
        "return exactly one object containing a complete revised candidate under the candidate key. The candidate "
        "must satisfy required_output_schema and cite visible evidence_anchor_ids. Return JSON only. Do not infer "
        "hidden or sealed benchmark material."
    ),
}
SENSITIVE_TERMS = (
    "secret", "sealed", "hidden", "answer", "target", "reference",
    "api_key", "access_token", "password", "authorization",
)
SENSITIVE_LOCATOR_KEYS = {"api_key_env", "api_key_required", "credential_target"}
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[a-z0-9_-]{8,}\b", re.IGNORECASE),
    re.compile(r"\bbearer\s+[a-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"://[^/\s:@]+:[^@\s/]+@", re.IGNORECASE),
    re.compile(
        r"[?&](?:api[_-]?key|access[_-]?token|token|password|authorization|key)=[^&#\s]+",
        re.IGNORECASE,
    ),
)


class QuestionSynthesisRunError(ValueError):
    """Raised when a frozen execution boundary or immutable output drifts."""


class _AuditedProviderCallError(RuntimeError):
    def __init__(self, reason_code: str, audit: dict[str, Any]):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.audit = audit


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    decoded = urllib.parse.unquote(relative)
    decoded_parts = [part.casefold() for part in re.split(r"[\\/]", decoded) if part]
    path_tokens = {
        token
        for part in decoded_parts
        for token in re.split(r"[^a-z0-9_]+", part)
        if token
    }
    if any(term in path_tokens for term in SENSITIVE_TERMS):
        raise QuestionSynthesisRunError(f"path contains a sensitive segment: {relative}")
    candidate = Path(relative)
    if candidate.is_absolute() or PureWindowsPath(relative).is_absolute() or ".." in candidate.parts:
        raise QuestionSynthesisRunError(f"path escapes the execution root: {relative}")
    resolved_root = root.resolve()
    resolved = (resolved_root / candidate).resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise QuestionSynthesisRunError(f"path escapes the execution root: {relative}")
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QuestionSynthesisRunError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise QuestionSynthesisRunError(f"JSON object required: {path}")
    return value


def _contains_sensitive(value: Any, *, path: str = "") -> bool:
    if isinstance(value, dict):
        return any(
            (
                str(key).casefold() not in SENSITIVE_LOCATOR_KEYS
                and any(term in str(key).casefold() for term in SENSITIVE_TERMS)
            )
            or _contains_sensitive(child, path=f"{path}/{key}")
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive(child, path=f"{path}/{index}") for index, child in enumerate(value))
    return isinstance(value, str) and any(
        term in {part.casefold() for part in Path(value).parts}
        for term in SENSITIVE_TERMS
    )


def _contains_literal_secret(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_literal_secret(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_literal_secret(child) for child in value)
    return isinstance(value, str) and any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)


def _versioned_prompt_hashes() -> dict[str, str]:
    return {
        key: hashlib.sha256(value.encode("utf-8")).hexdigest()
        for key, value in PROMPT_TEMPLATES.items()
    }


def _validate_hash_map(root: Path, values: dict[str, str], *, label: str) -> None:
    for relative, expected in values.items():
        if _contains_sensitive(relative):
            raise QuestionSynthesisRunError(f"{label} path contains sensitive segment")
        path = _safe_path(root, relative)
        if not path.is_file() or _sha256_file(path) != expected:
            raise QuestionSynthesisRunError(f"{label} hashes require root-relative existing files")


def validate_execution_plan(plan: dict[str, Any], *, root: Path) -> None:
    if isinstance(plan.get("matched_budget"), dict) and plan["matched_budget"].get("retry_budget") not in (None, 0):
        raise QuestionSynthesisRunError("nonzero retry budget is unsupported; frozen runs use no retries")
    try:
        validate_document(plan, "question_synthesis_execution_plan")
    except (SchemaValidationError, FileNotFoundError) as exc:
        raise QuestionSynthesisRunError(str(exc)) from exc
    if tuple(plan["configuration_ids"]) != CONFIGURATION_IDS:
        raise QuestionSynthesisRunError("exact five configuration IDs are required")
    if tuple(plan["seeds"]) != ORCHESTRATION_SEEDS:
        raise QuestionSynthesisRunError("exact orchestration seeds are required")
    if plan["provider_seed_supported"] is not False:
        raise QuestionSynthesisRunError("provider seed support must not be claimed")

    provider_path = _safe_path(root, plan["provider_config_path"])
    if not provider_path.is_file() or _sha256_file(provider_path) != plan["provider_config_sha256"]:
        raise QuestionSynthesisRunError("provider configuration SHA-256 drift")
    provider_config = _read_json(provider_path)
    if provider_config.get("model") != plan["model_reference"]:
        raise QuestionSynthesisRunError("provider model reference drift")
    if _contains_sensitive(provider_config):
        raise QuestionSynthesisRunError("provider configuration contains a secret value")
    try:
        validate_document(provider_config, "provider_config")
    except (SchemaValidationError, FileNotFoundError) as exc:
        raise QuestionSynthesisRunError(f"provider configuration schema rejected: {exc}") from exc
    if _contains_literal_secret(provider_config):
        raise QuestionSynthesisRunError("provider configuration contains a literal secret pattern")
    expected_timeout = plan["budget_enforcement"]["provider_timeout_seconds"]
    if provider_config.get("timeout_seconds") != expected_timeout:
        raise QuestionSynthesisRunError(
            "provider configuration timeout does not match frozen budget enforcement"
        )
    if plan["prompt_sha256_by_configuration"] != _versioned_prompt_hashes():
        raise QuestionSynthesisRunError("prompt template SHA-256 drift")
    _validate_hash_map(root, plan["tool_version_sha256"], label="tool version")
    _validate_hash_map(root, plan["source_version_sha256"], label="source version")
    required_tools = {
        "metawingman/scripts/metawingman_core/question_synthesis_runner.py": Path(__file__).resolve(),
        "metawingman/scripts/metawingman_core/question_synthesis_design.py": Path(__file__).resolve().with_name("question_synthesis_design.py"),
    }
    if any(
        plan["tool_version_sha256"].get(relative) != _sha256_file(runtime_path)
        for relative, runtime_path in required_tools.items()
    ):
        raise QuestionSynthesisRunError("tool hash closure must bind the actual runner and design implementation")
    registry_relative = "metawingman/references/question-synthesis-methods.json"
    registry_runtime = Path(__file__).resolve().parents[2] / "references" / "question-synthesis-methods.json"
    if plan["source_version_sha256"].get(registry_relative) != _sha256_file(registry_runtime):
        raise QuestionSynthesisRunError("method registry hash closure is missing or drifted")

    case_ids: list[str] = []
    for item in plan["cases"]:
        case_id = item["case_id"]
        if case_id in case_ids:
            raise QuestionSynthesisRunError(f"duplicate case_id: {case_id}")
        case_ids.append(case_id)
        case_path = _safe_path(root, item["operational_case_path"])
        if not case_path.is_file() or _sha256_file(case_path) != item["sha256"]:
            raise QuestionSynthesisRunError(f"case SHA-256 drift: {case_id}")
        case = _read_json(case_path)
        if _contains_sensitive(case):
            raise QuestionSynthesisRunError(
                f"operational case contains hidden or sealed material: {case_id}"
            )
        if case.get("case_id") != case_id:
            raise QuestionSynthesisRunError(f"case_id drift in operational case: {case_id}")
        if case.get("split") != plan["split"]:
            raise QuestionSynthesisRunError(f"case split must equal plan split: {case_id}")

    expected = {
        (case_id, configuration_id, seed)
        for case_id in case_ids
        for configuration_id in CONFIGURATION_IDS
        for seed in ORCHESTRATION_SEEDS
    }
    observed: set[tuple[str, str, int]] = set()
    output_paths: set[str] = set()
    receipt_paths: set[str] = set()
    for slot in plan["slots"]:
        key = (slot["case_id"], slot["configuration_id"], slot["seed"])
        if key in observed:
            raise QuestionSynthesisRunError(f"duplicate configuration-seed slot: {key}")
        observed.add(key)
        for field, paths in (("output_path", output_paths), ("receipt_path", receipt_paths)):
            relative = slot[field]
            _safe_path(root, relative)
            if relative in paths:
                raise QuestionSynthesisRunError(f"duplicate {field}: {relative}")
            paths.add(relative)
    missing = expected - observed
    extra = observed - expected
    if missing:
        raise QuestionSynthesisRunError(f"missing configuration-seed slots: {sorted(missing)}")
    if extra:
        raise QuestionSynthesisRunError(f"unregistered configuration-seed slots: {sorted(extra)}")


def sanitize_arm_result(configuration_id: str, result: dict[str, Any]) -> dict[str, Any]:
    if configuration_id not in CONFIGURATION_IDS:
        raise QuestionSynthesisRunError(f"unknown configuration_id: {configuration_id}")
    sanitized = dict(result)
    sanitized["configuration_id"] = configuration_id
    sanitized["is_ablation"] = configuration_id != "full-biomedical-stack"
    if sanitized["is_ablation"]:
        sanitized.pop("verifier_observations", None)
        sanitized.pop("verification_evidence", None)
    return sanitized


def enforce_full_stack_verification(result: dict[str, Any]) -> dict[str, Any]:
    observations = {
        item.get("verifier_id"): item.get("status")
        for item in result.get("verifier_observations", [])
    }
    required = ("source", "executable")
    if any(observations.get(verifier_id) != "passed" for verifier_id in required):
        blocked = dict(result)
        blocked["status"] = "blocked"
        blocked["reason_codes"] = sorted(set(
            [*blocked.get("reason_codes", []), "full_stack_hard_verifier_failed"]
        ))
        blocked.pop("candidate", None)
        return blocked
    return result


def _capabilities(configuration_id: str) -> dict[str, bool]:
    levels = {
        "general-model-baseline": 0,
        "generic-retrieval": 1,
        "biomedical-schema": 2,
        "biomedical-routing": 3,
        "full-biomedical-stack": 4,
    }
    if configuration_id not in levels:
        raise QuestionSynthesisRunError(f"unknown configuration_id: {configuration_id}")
    level = levels[configuration_id]
    return {
        "generic_retrieval": level >= 1,
        "biomedical_schema": level >= 2,
        "terminology_retrieval": level >= 3,
        "deterministic_routing": level >= 3,
        "evidence_graph": level >= 4,
        "document_state": level >= 4,
        "external_verifier": level >= 4,
        "opposition_judge": configuration_id in {"generic-retrieval", "full-biomedical-stack"},
        "abstention": level >= 4,
    }


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _clinical_context(case: dict[str, Any]) -> dict[str, Any]:
    context = dict(case.get("clinical_context") or {})
    source_query_value = case.get("source_query") or ""
    if isinstance(source_query_value, dict):
        source_query = str(
            source_query_value.get("broad_topic_seed")
            or source_query_value.get("query")
            or ""
        ).strip()
    else:
        source_query = str(source_query_value).strip()
    brief = case.get("decision_brief")
    if isinstance(brief, dict):
        brief_text = " ".join(str(value) for value in brief.values())
    else:
        brief_text = str(brief or "")
    if not brief_text:
        for material in case.get("visible_material", []):
            if str(material.get("material_id", "")).startswith("decision-brief-"):
                try:
                    parsed = json.loads(str(material.get("text", "")))
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    brief_text = str(parsed.get("task") or "")
                break
    if not context.get("decision_problem"):
        context["decision_problem"] = source_query or brief_text
    if brief_text:
        context.setdefault("decision_brief", brief_text)
    return context


def _normalized_material(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized.setdefault("text", item.get("content", item.get("abstract", "")))
    normalized.setdefault("source_node_ids", item.get("source_node_ids", [item["source_id"]] if item.get("source_id") else []))
    normalized.setdefault("document_state", "derived_visible_material")
    return normalized


def _retrieve_visible_material(
    case: dict[str, Any], *, seed: int, terminology_aware: bool
) -> list[dict[str, Any]]:
    query = " ".join(str(value) for value in _clinical_context(case).values())
    query_words = _words(query)
    if terminology_aware:
        expansions = {
            "mortality": {"death", "survival"},
            "intervention": {"treatment", "therapy"},
            "diagnostic": {"diagnosis", "sensitivity", "specificity"},
        }
        query_words |= {
            expanded
            for term in tuple(query_words)
            for expanded in expansions.get(term, set())
        }
    rng = random.Random(seed)
    scored: list[tuple[int, float, str, dict[str, Any]]] = []
    for raw_item in case.get("visible_material", []):
        item = _normalized_material(raw_item)
        score = len(query_words & _words(str(item.get("text", ""))))
        scored.append((-score, rng.random(), str(item.get("material_id", "")), item))
    return [item for _, _, _, item in sorted(scored)]


def _public_method_registry() -> list[dict[str, Any]]:
    registry_path = Path(__file__).resolve().parents[2] / "references" / "question-synthesis-methods.json"
    try:
        routes = _read_json(registry_path).get("routes", [])
    except QuestionSynthesisRunError:
        return []
    return [item for item in routes if isinstance(item, dict) and item.get("route_id")]


def _deterministic_route(case: dict[str, Any]) -> str | None:
    public_routes = {str(item["route_id"]) for item in _public_method_registry()}
    recommended = {
        str(item.get("route_id"))
        for item in case.get("route_recommendations", [])
        if item.get("route_id")
    }
    declared = {
        str(item.get("route_id"))
        for item in [*case.get("method_routes", []), *case.get("route_registry", [])]
        if item.get("route_id")
    }
    eligible = sorted(public_routes & (recommended or declared))
    if eligible:
        return eligible[0]
    words = _words(" ".join(str(value) for value in _clinical_context(case).values()))
    rules = (
        ({"diagnostic", "detection", "screening", "accuracy", "biomarker"}, "diagnostic_bivariate_hsroc"),
        ({"prognostic", "prognosis", "mortality", "survival", "predictor"}, "prognostic_factor_meta"),
        ({"prevalence", "proportion", "burden"}, "prevalence_random_effects"),
        ({"harm", "harms", "hepatotoxicity", "toxicity", "adverse", "safety"}, "rare_event_harms"),
        ({"intervention", "exercise", "therapy", "treatment", "rehabilitation", "efficacy", "effectiveness"}, "pairwise_random_effects"),
    )
    scored = [
        (len(triggers & words), route_id)
        for triggers, route_id in rules
        if route_id in public_routes
    ]
    best_score = max((score for score, _ in scored), default=0)
    winners = sorted(route_id for score, route_id in scored if score == best_score and score > 0)
    return winners[0] if len(winners) == 1 else None


def prepare_arm_input(
    configuration_id: str, case: dict[str, Any], *, seed: int
) -> dict[str, Any]:
    """Build the capability-bounded operational input for one ablation arm."""
    capabilities = _capabilities(configuration_id)
    visible = []
    if capabilities["generic_retrieval"]:
        visible = _retrieve_visible_material(
            case,
            seed=seed,
            terminology_aware=capabilities["terminology_retrieval"],
        )
    payload: dict[str, Any] = {
        "case_id": case["case_id"],
        "clinical_context": _clinical_context(case),
    }
    if visible:
        payload["retrieved_visible_material"] = [
            {"material_id": item.get("material_id"), "text": item.get("text")}
            for item in visible
        ]
    if capabilities["biomedical_schema"]:
        payload["required_output_schema"] = {
            "review_family": "string",
            "synthesis_route": "string",
            "population": "string",
            "intervention_or_exposure": "string",
            "comparator": "string",
            "outcomes": "array[string]",
        }
        if capabilities["external_verifier"]:
            payload["required_output_schema"]["evidence_anchor_ids"] = "array[string]"
    if capabilities["deterministic_routing"]:
        payload["deterministic_route"] = _deterministic_route(case)
        payload["executable_method_registry"] = [
            {
                "route_id": item["route_id"],
                "review_families": item.get("review_families", []),
                "required_checks": item.get("required_checks", []),
                "r_adapter": item.get("r_adapter"),
            }
            for item in _public_method_registry()
        ]
    if capabilities["evidence_graph"]:
        payload["evidence_graph"] = [
            {
                "material_id": item.get("material_id"),
                "source_node_ids": item.get("source_node_ids", []),
            }
            for item in visible
        ]
    if capabilities["document_state"]:
        payload["document_states"] = {
            str(item.get("material_id")): item.get("document_state")
            for item in visible
        }
    return {
        "configuration_id": configuration_id,
        "seed": seed,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "capabilities": capabilities,
        "payload": payload,
    }


def _provider_call(
    provider: Any,
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = provider.chat(
        messages,
        model=model,
        max_tokens=max_tokens,
        json_output=True,
    )
    audit = result.audit_record(include_content=False)
    if audit.get("model") != model:
        raise _AuditedProviderCallError("provider_model_mismatch", audit)
    try:
        document = json.loads(result.content)
    except (TypeError, json.JSONDecodeError):
        raise _AuditedProviderCallError("provider_output_invalid", audit) from None
    if not isinstance(document, dict):
        raise _AuditedProviderCallError("provider_output_invalid", audit)
    return document, audit


def _hard_verifier_observations(
    candidate: dict[str, Any], case: dict[str, Any]
) -> list[dict[str, str]]:
    visible_sources = {
        str(source_id)
        for raw_item in case.get("visible_material", [])
        for source_id in _normalized_material(raw_item).get("source_node_ids", [])
    }
    anchors = {str(value) for value in candidate.get("evidence_anchor_ids", [])}
    route = str(candidate.get("synthesis_route") or "")
    review_family = str(candidate.get("review_family") or "")
    route_entry = next(
        (item for item in _public_method_registry() if str(item.get("route_id")) == route),
        None,
    )
    executable = bool(
        route_entry
        and review_family in route_entry.get("review_families", [])
        and route_entry.get("r_adapter")
    )
    return [
        {
            "verifier_id": "source",
            "status": "passed" if anchors and anchors.issubset(visible_sources) else "failed",
        },
        {
            "verifier_id": "executable",
            "status": "passed" if executable else "failed",
        },
    ]


def _followup_role_context(
    prepared: dict[str, Any],
    *,
    role: str,
    candidate: dict[str, Any],
    opposition: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep later deliberation calls source-auditable without replaying full text."""
    payload = prepared["payload"]
    review_family = str(candidate.get("review_family") or "")
    route_id = str(candidate.get("synthesis_route") or "")
    eligible_route_ids = {route_id, str(payload.get("deterministic_route") or "")}
    eligible_methods = [
        item
        for item in payload.get("executable_method_registry", [])
        if item.get("r_adapter")
        and str(item.get("route_id")) in eligible_route_ids
        and (not review_family or review_family in item.get("review_families", []))
    ]
    evidence_anchor_ids = sorted({
        str(anchor)
        for item in payload.get("evidence_graph", [])
        for anchor in item.get("source_node_ids", [])
    })
    document_state_counts: dict[str, int] = {}
    for state in payload.get("document_states", {}).values():
        key = str(state)
        document_state_counts[key] = document_state_counts.get(key, 0) + 1
    context: dict[str, Any] = {
        "configuration_id": prepared["configuration_id"],
        "seed": prepared["seed"],
        "seed_scope": prepared["seed_scope"],
        "role": role,
        "proposal_candidate": candidate,
        "review_contract": {
            "required_output_schema": payload.get("required_output_schema", {}),
            "deterministic_route": payload.get("deterministic_route"),
            "eligible_executable_methods": eligible_methods,
            "visible_evidence_anchor_ids": evidence_anchor_ids,
            "document_state_counts": document_state_counts,
        },
    }
    if opposition is not None:
        context["opposition"] = opposition
    return context


def _required_response_shape(role: str) -> dict[str, str]:
    if role == "opposition":
        return {"critique": "array of concise scientific objections"}
    if role == "judge":
        return {"candidate": "complete revised candidate object"}
    return {"candidate": "complete candidate object; proposal role may return it unwrapped"}


def run_configuration(
    configuration_id: str,
    case: dict[str, Any],
    *,
    seed: int,
    provider: Any,
    model: str,
    max_output_tokens: int,
    max_model_calls: int = 3,
    wall_time_ceiling_seconds: float = float("inf"),
) -> dict[str, Any]:
    """Execute one real capability arm; provider stochasticity is not seeded."""
    prepared = prepare_arm_input(configuration_id, case, seed=seed)
    capabilities = prepared["capabilities"]
    roles = ["direct"]
    if capabilities["opposition_judge"]:
        roles = ["proposal", "opposition", "judge"]
    per_call_tokens = max(1, max_output_tokens // len(roles))
    provider_receipts: list[dict[str, Any]] = []
    candidate: dict[str, Any] | None = None
    opposition: dict[str, Any] | None = None
    role_outputs: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        for role in roles:
            if len(provider_receipts) >= max_model_calls:
                return sanitize_arm_result(configuration_id, {
                    "status": "blocked",
                    "reason_codes": ["model_call_budget_exhausted_before_call"],
                    "role_outputs": role_outputs,
                    "_provider_receipts": provider_receipts,
                    "same_provider_roles_are_independent_evidence": False,
                })
            if time.perf_counter() - wall_start >= wall_time_ceiling_seconds:
                return sanitize_arm_result(configuration_id, {
                    "status": "blocked",
                    "reason_codes": ["wall_time_budget_exhausted_before_call"],
                    "role_outputs": role_outputs,
                    "_provider_receipts": provider_receipts,
                    "same_provider_roles_are_independent_evidence": False,
                })
            role_context: dict[str, Any]
            if candidate is None:
                role_context = {"role": role, **prepared}
            else:
                role_context = _followup_role_context(
                    prepared,
                    role=role,
                    candidate=candidate,
                    opposition=opposition,
                )
            role_context["required_response_shape"] = _required_response_shape(role)
            messages = [
            {
                "role": "system",
                "content": PROMPT_TEMPLATES[configuration_id],
            },
            {
                "role": "user",
                "content": json.dumps(
                    role_context, sort_keys=True, ensure_ascii=False
                ),
            },
            ]
            try:
                document, receipt = _provider_call(
                    provider, messages, model=model, max_tokens=per_call_tokens
                )
            except _AuditedProviderCallError as exc:
                provider_receipts.append(exc.audit)
                role_outputs.append({"role": role, "output_sha256": exc.audit["content_sha256"]})
                reason_codes = [exc.reason_code]
                if exc.reason_code != "provider_output_invalid":
                    reason_codes.insert(0, "provider_execution_failed")
                return sanitize_arm_result(configuration_id, {
                    "status": "failed",
                    "reason_codes": reason_codes,
                    "role_outputs": role_outputs,
                    "_provider_receipts": provider_receipts,
                    "same_provider_roles_are_independent_evidence": False,
                })
            provider_receipts.append(receipt)
            role_outputs.append({"role": role, "output_sha256": receipt["content_sha256"]})
            if candidate is None:
                candidate = document.get("candidate", document)
                if not isinstance(candidate, dict):
                    raise QuestionSynthesisRunError("candidate output must be a JSON object")
            elif role == "opposition":
                opposition = document
            elif role == "judge":
                judged_candidate = document.get("candidate")
                if not isinstance(judged_candidate, dict):
                    return sanitize_arm_result(configuration_id, {
                        "status": "blocked", "reason_codes": ["judge_candidate_missing"],
                        "role_outputs": role_outputs, "_provider_receipts": provider_receipts,
                        "same_provider_roles_are_independent_evidence": False,
                    })
                candidate = judged_candidate
    except Exception:
        return sanitize_arm_result(configuration_id, {
            "status": "failed", "reason_codes": ["provider_execution_failed"],
            "role_outputs": role_outputs, "_provider_receipts": provider_receipts,
            "same_provider_roles_are_independent_evidence": False,
        })
    result: dict[str, Any] = {
        "status": "selected",
        "candidate": candidate,
        "role_outputs": role_outputs,
        "capabilities": capabilities,
        "same_provider_roles_are_independent_evidence": False,
        "_provider_receipts": provider_receipts,
    }
    if configuration_id == "full-biomedical-stack":
        result["verifier_observations"] = _hard_verifier_observations(candidate or {}, case)
        result = enforce_full_stack_verification(result)
    return sanitize_arm_result(configuration_id, result)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sum_optional(receipts: list[dict[str, Any]], field: str) -> int | None:
    values = [receipt.get(field) for receipt in receipts]
    return None if any(value is None for value in values) else sum(int(value) for value in values)


def resume_slot(plan: dict[str, Any], slot: dict[str, Any], *, root: Path) -> dict[str, Any] | None:
    output_path = _safe_path(root, slot["output_path"])
    receipt_path = _safe_path(root, slot["receipt_path"])
    if not output_path.exists() and not receipt_path.exists():
        return None
    if not output_path.is_file() or not receipt_path.is_file():
        raise QuestionSynthesisRunError("partial existing slot output cannot be resumed")
    receipt = _read_json(receipt_path)
    required_receipt = {
        "plan_id", "case_id", "configuration_id", "seed", "provider_seed_supported",
        "seed_scope", "same_provider_roles_are_independent_evidence", "started_at_utc",
        "ended_at_utc", "wall_time_seconds", "cpu_seconds", "gpu_seconds", "peak_memory_bytes",
        "storage_growth_bytes", "model_calls", "input_tokens", "output_tokens", "provider_cost",
        "provider_cost_status", "status", "reason_codes", "output_path", "output_sha256",
        "prompt_sha256", "tool_version_sha256", "model_reference", "provider_config_sha256",
        "source_version_sha256", "matched_budget", "command_argv",
        "budget_enforcement",
    }
    if not required_receipt.issubset(receipt):
        raise QuestionSynthesisRunError("existing receipt contract is incomplete")
    expected = {
        "plan_id": plan["plan_id"],
        "case_id": slot["case_id"],
        "configuration_id": slot["configuration_id"],
        "seed": slot["seed"],
        "output_path": slot["output_path"],
        "provider_config_sha256": plan["provider_config_sha256"],
        "prompt_sha256": plan["prompt_sha256_by_configuration"][slot["configuration_id"]],
        "model_reference": plan["model_reference"],
        "tool_version_sha256": plan["tool_version_sha256"],
        "source_version_sha256": plan["source_version_sha256"],
        "budget_enforcement": plan["budget_enforcement"],
        "provider_seed_supported": False,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "matched_budget": plan["matched_budget"],
        "command_argv": plan["command_argv"],
        "same_provider_roles_are_independent_evidence": False,
    }
    drift = [field for field, value in expected.items() if receipt.get(field) != value]
    if drift:
        raise QuestionSynthesisRunError(f"existing receipt slot/hash drift: {drift}")
    if _sha256_file(output_path) != receipt.get("output_sha256"):
        raise QuestionSynthesisRunError("output SHA-256 drift")
    return {"status": "already_completed", "receipt": receipt}


def execute_slot(
    plan: dict[str, Any],
    slot: dict[str, Any],
    *,
    root: Path,
    provider: Any,
) -> dict[str, Any]:
    """Execute one immutable slot or safely resume its hash-matching receipt."""
    validate_execution_plan(plan, root=root)
    registered_slots = {
        (item["case_id"], item["configuration_id"], item["seed"]): item
        for item in plan["slots"]
    }
    key = (slot.get("case_id"), slot.get("configuration_id"), slot.get("seed"))
    registered = registered_slots.get(key)
    if registered != slot:
        raise QuestionSynthesisRunError("slot is not exactly frozen in the execution plan")
    resumed = resume_slot(plan, slot, root=root)
    if resumed is not None:
        return resumed
    case_entry = next(item for item in plan["cases"] if item["case_id"] == slot["case_id"])
    case = _read_json(_safe_path(root, case_entry["operational_case_path"]))

    started_at = _utc_now()
    wall_start = time.perf_counter()
    cpu_start = time.process_time()
    tracemalloc.start()
    try:
        try:
            result = run_configuration(
                slot["configuration_id"],
                case,
                seed=slot["seed"],
                provider=provider,
                model=plan["model_reference"],
                max_output_tokens=plan["matched_budget"]["max_output_tokens"],
                max_model_calls=plan["matched_budget"]["max_model_calls"],
                wall_time_ceiling_seconds=plan["matched_budget"]["wall_time_ceiling_seconds"],
            )
        except Exception:
            result = {
                "status": "failed",
                "reason_codes": ["provider_execution_failed"],
                "configuration_id": slot["configuration_id"],
                "is_ablation": slot["configuration_id"] != "full-biomedical-stack",
                "same_provider_roles_are_independent_evidence": False,
            }
        _, peak_memory = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    wall_time = time.perf_counter() - wall_start
    cpu_time = time.process_time() - cpu_start
    provider_receipts = list(result.pop("_provider_receipts", []))
    model_calls = len(provider_receipts)
    input_tokens = _sum_optional(provider_receipts, "prompt_tokens")
    output_tokens = _sum_optional(provider_receipts, "completion_tokens")
    budget = plan["matched_budget"]
    violations: list[str] = []
    if model_calls is not None and model_calls > budget["max_model_calls"]:
        violations.append("max_model_calls")
    if input_tokens is not None and input_tokens > budget["max_input_tokens"]:
        violations.append("max_input_tokens")
    if output_tokens is not None and output_tokens > budget["max_output_tokens"]:
        violations.append("max_output_tokens")
    if wall_time > budget["wall_time_ceiling_seconds"]:
        violations.append("wall_time_ceiling_seconds")
    if violations:
        result = {
            "status": "blocked",
            "reason_codes": ["matched_budget_ceiling_exceeded", *sorted(violations)],
            "configuration_id": slot["configuration_id"],
            "is_ablation": slot["configuration_id"] != "full-biomedical-stack",
            "same_provider_roles_are_independent_evidence": False,
        }

    output_path = _safe_path(root, slot["output_path"])
    receipt_path = _safe_path(root, slot["receipt_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_bytes = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with output_path.open("xb") as handle:
            handle.write(output_bytes)
    except FileExistsError as exc:
        raise QuestionSynthesisRunError(f"refusing to overwrite output: {output_path}") from exc
    output_sha = hashlib.sha256(output_bytes).hexdigest()
    receipt = {
        "plan_id": plan["plan_id"],
        "case_id": slot["case_id"],
        "configuration_id": slot["configuration_id"],
        "seed": slot["seed"],
        "provider_seed_supported": False,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "same_provider_roles_are_independent_evidence": False,
        "started_at_utc": started_at,
        "ended_at_utc": _utc_now(),
        "wall_time_seconds": wall_time,
        "cpu_seconds": cpu_time,
        "gpu_seconds": None,
        "peak_memory_bytes": peak_memory,
        "storage_growth_bytes": 0,
        "model_calls": model_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "provider_cost": None,
        "provider_cost_status": "unknown",
        "status": result["status"],
        "reason_codes": result.get("reason_codes", []),
        "output_path": slot["output_path"],
        "output_sha256": output_sha,
        "prompt_sha256": plan["prompt_sha256_by_configuration"][slot["configuration_id"]],
        "tool_version_sha256": plan["tool_version_sha256"],
        "model_reference": plan["model_reference"],
        "provider_config_sha256": plan["provider_config_sha256"],
        "source_version_sha256": plan["source_version_sha256"],
        "matched_budget": budget,
        "budget_enforcement": plan["budget_enforcement"],
        "command_argv": plan["command_argv"],
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_text = ""
    for _ in range(8):
        receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
        measured = len(output_bytes) + len(receipt_text.encode("utf-8"))
        if receipt["storage_growth_bytes"] == measured:
            break
        receipt["storage_growth_bytes"] = measured
    receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    try:
        with receipt_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(receipt_text)
    except FileExistsError as exc:
        raise QuestionSynthesisRunError(f"refusing to overwrite receipt: {receipt_path}") from exc
    return {"status": "completed", "result": result, "receipt": receipt}


def execute_plan(
    plan: dict[str, Any],
    *,
    root: Path,
    validate_only: bool = False,
    provider_factory: Callable[[dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    validate_execution_plan(plan, root=root)
    if plan["status"] != "frozen":
        raise QuestionSynthesisRunError("execution requires a frozen plan")
    if validate_only:
        return {"status": "validated", "slots": len(plan["slots"]), "provider_calls": 0}
    if provider_factory is None:
        raise QuestionSynthesisRunError("provider_factory is required for execution")
    provider_config = _read_json(_safe_path(root, plan["provider_config_path"]))
    try:
        provider = provider_factory(provider_config)
    except Exception:
        raise QuestionSynthesisRunError("provider initialization failed") from None
    observed_timeout = getattr(provider, "timeout_seconds", None)
    expected_timeout = plan["budget_enforcement"]["provider_timeout_seconds"]
    if observed_timeout != expected_timeout:
        raise QuestionSynthesisRunError(
            f"provider timeout does not match frozen budget enforcement: {observed_timeout} != {expected_timeout}"
        )
    results = []
    systemic_failures = 0
    for slot in plan["slots"]:
        item = execute_slot(plan, slot, root=root, provider=provider)
        results.append(item)
        receipt = item.get("receipt", {})
        if receipt.get("status") == "failed" and "provider_execution_failed" in receipt.get("reason_codes", []):
            systemic_failures += 1
            if systemic_failures >= plan["failure_policy"]["max_systemic_provider_failures"]:
                break
    statuses = [item.get("receipt", {}).get("status") for item in results]
    return {
        "status": "stopped" if systemic_failures else "executed",
        "slots": len(results),
        "completed": sum(item["status"] == "completed" for item in results),
        "resumed": sum(item["status"] == "already_completed" for item in results),
        "successful": statuses.count("selected"), "failed": statuses.count("failed"),
        "blocked": statuses.count("blocked"), "systemic_stop": bool(systemic_failures),
    }


def freeze_execution_plan(
    draft_path: Path,
    frozen_path: Path,
    *,
    frozen_at_utc: str | None = None,
) -> dict[str, Any]:
    """Freeze a complete draft without contacting or constructing a provider."""
    if frozen_path.exists():
        raise QuestionSynthesisRunError(f"freeze output already exists: {frozen_path}")
    draft = _read_json(draft_path)
    root = draft_path.resolve().parent
    validate_execution_plan(draft, root=root)
    if draft["status"] != "draft":
        raise QuestionSynthesisRunError("only a draft execution plan can be frozen")
    frozen = dict(draft)
    frozen["status"] = "frozen"
    frozen["frozen_at_utc"] = frozen_at_utc or _utc_now()
    validate_execution_plan(frozen, root=root)
    frozen_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with frozen_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(frozen, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise QuestionSynthesisRunError(
            f"freeze output already exists: {frozen_path}"
        ) from exc
    return frozen


def lock_split(plan_path: Path, lock_path: Path) -> dict[str, Any]:
    plan = _read_json(plan_path)
    root = plan_path.resolve().parent
    validate_execution_plan(plan, root=root)
    if plan["status"] != "frozen":
        raise QuestionSynthesisRunError("split lock requires a frozen execution plan")
    completed = 0
    for slot in plan["slots"]:
        try:
            resumed = resume_slot(plan, slot, root=root)
        except QuestionSynthesisRunError:
            raise
        if resumed is not None:
            completed += 1
    required = 15 * len(plan["cases"])
    if completed != required:
        raise QuestionSynthesisRunError(
            f"split lock requires 15 completed slots per case; found {completed}/{required}"
        )
    if lock_path.exists():
        raise QuestionSynthesisRunError(f"lock output already exists: {lock_path}")
    lock = {
        "plan_id": plan["plan_id"],
        "split": plan["split"],
        "completed_slots": completed,
        "plan_sha256": _sha256_file(plan_path),
        "status": "locked",
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return lock
