"""Fail-closed contracts for blind end-to-end review reconstruction.

The execution controller may know the sealed file locator and checksum, but an
executor receives only operational case documents.  Published expert
references are read only by :func:`unlock_reference`, after the complete
case-by-configuration-by-seed receipt set has been locked.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

from .schema_guard import SchemaValidationError, validate_document


class EndToEndReconstructionError(ValueError):
    """Raised when a reconstruction plan or lock set is unsafe or incomplete."""


_SEALED_OR_SECRET_KEYS = {
    "answer", "answers", "api_key", "access_token", "authorization",
    "credentials", "doi", "password", "published_expert_reference",
    "sealed_target", "target_authors", "target_doi", "target_title",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _normal_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold().replace("-", "_")


def _contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normal_key(str(key))
            if normalized in _SEALED_OR_SECRET_KEYS or normalized.endswith(("_password", "_secret", "_token")):
                return True
            if _contains_sensitive(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_sensitive(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)
    return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EndToEndReconstructionError(message)


def _load_operational_case(entry: dict[str, Any], operational_root: Path) -> dict[str, Any]:
    path = Path(entry.get("operational_path", ""))
    _require(path.is_file() and _within(path, operational_root), "operational path is missing or outside operational root")
    _require(not any(part.casefold() in {"sealed", "hidden", "answer", "answers"} for part in path.parts),
             "operational path contains a sealed or answer-bearing component")
    expected = entry.get("operational_sha256")
    _require(isinstance(expected, str) and _SHA256.fullmatch(expected) is not None, "invalid operational SHA-256")
    _require(_sha256(path) == expected, f"operational hash drift: {entry.get('case_id', '<unknown>')}")
    try:
        case = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EndToEndReconstructionError("operational case is not valid UTF-8 JSON") from exc
    _require(not _contains_sensitive(case), "operational case contains sensitive or sealed material")
    _require(case.get("case_id") == entry.get("case_id"), "case_id binding mismatch")
    _require(case.get("review_family_id") == entry.get("review_family_id"), "review family binding mismatch")
    _require(case.get("split") == entry.get("split"), "split binding mismatch")
    license_record = case.get("license")
    _require(isinstance(license_record, dict) and license_record.get("status") == "verified",
             "case license is not verified")
    _require(isinstance(case.get("reproduction_ceiling"), str) and bool(case["reproduction_ceiling"].strip()),
             "case reproduction ceiling is missing")
    _require(isinstance(case.get("historical_cutoff_at_utc"), str), "historical cutoff is missing")
    return case


def validate_execution_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate a frozen factorial plan without opening published references."""
    try:
        validate_document(plan, "end_to_end_reconstruction_plan")
    except (FileNotFoundError, SchemaValidationError) as exc:
        raise EndToEndReconstructionError(str(exc)) from exc
    _require(isinstance(plan, dict) and plan.get("schema_version") == "1.0", "unsupported execution plan")
    plan_id = plan.get("plan_id")
    _require(isinstance(plan_id, str) and bool(plan_id.strip()), "plan_id is required")
    _require(isinstance(plan.get("frozen_at_utc"), str), "frozen_at_utc is required")
    operational_root = Path(plan.get("operational_root", ""))
    sealed_root = Path(plan.get("sealed_root", ""))
    _require(operational_root.is_dir(), "operational root is missing")
    _require(sealed_root.is_dir() and not _within(sealed_root, operational_root),
             "sealed root is missing or nested in operational root")

    runtime = plan["runtime"]
    bindings = [
        {"path": runtime["provider_config_path"], "sha256": runtime["provider_config_sha256"]},
        *runtime["prompt_files"], *runtime["tool_files"],
    ]
    for binding in bindings:
        path = Path(binding["path"])
        _require(path.is_file() and _within(path, operational_root), "runtime file is missing or outside operational root")
        _require(_sha256(path) == binding["sha256"], f"runtime hash drift: {path.name}")
    try:
        provider_config = json.loads(Path(runtime["provider_config_path"]).read_text(encoding="utf-8"))
        validate_document(provider_config, "provider_config")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise EndToEndReconstructionError(f"invalid provider configuration: {exc}") from exc
    _require(not _contains_sensitive(provider_config), "provider configuration contains a literal secret")
    _require(provider_config.get("model") == runtime["model_id"], "provider model does not match frozen runtime model")

    configurations = plan.get("configurations")
    _require(isinstance(configurations, list) and len(configurations) == 4,
             "exact four-arm innovation factorial is required")
    config_ids: list[str] = []
    capability_pairs: set[tuple[bool, bool]] = set()
    for config in configurations:
        _require(isinstance(config, dict), "configuration must be an object")
        config_id = config.get("configuration_id")
        _require(isinstance(config_id, str) and bool(config_id.strip()), "configuration_id is required")
        config_ids.append(config_id)
        pair = (config.get("topic_opportunity_control"), config.get("conclusion_directed_acquisition"))
        _require(all(isinstance(flag, bool) for flag in pair), "innovation flags must be boolean")
        capability_pairs.add(pair)
    _require(len(set(config_ids)) == 4 and capability_pairs == {(False, False), (True, False), (False, True), (True, True)},
             "configurations do not identify the complete two-innovation factorial")

    seeds = plan.get("seeds")
    _require(isinstance(seeds, list) and len(seeds) == 3 and len(set(seeds)) == 3
             and all(isinstance(seed, int) and not isinstance(seed, bool) for seed in seeds),
             "exactly three unique integer seeds are required")
    cases = plan.get("cases")
    _require(isinstance(cases, list) and len(cases) >= 2, "at least two reconstruction cases are required")
    case_ids: list[str] = []
    family_splits: dict[str, str] = {}
    for entry in cases:
        _require(isinstance(entry, dict), "case entry must be an object")
        case = _load_operational_case(entry, operational_root)
        case_id = entry["case_id"]
        _require(case_id not in case_ids, f"duplicate case_id: {case_id}")
        case_ids.append(case_id)
        split = entry["split"]
        closure = {entry["review_family_id"], *case.get("dependency_family_ids", [])}
        for family in closure:
            prior = family_splits.setdefault(family, split)
            _require(prior == split, f"review family or dependency {family} crosses splits")
        sealed_path = Path(entry.get("sealed_reference_path", ""))
        _require(_within(sealed_path, sealed_root), "sealed reference path is outside sealed root")
        sealed_hash = entry.get("sealed_reference_sha256")
        _require(isinstance(sealed_hash, str) and _SHA256.fullmatch(sealed_hash) is not None,
                 "invalid sealed reference SHA-256")
    _require(len(set(entry["review_family_id"] for entry in cases)) >= 2,
             "at least two materially different review families are required")

    slots = plan.get("slots")
    _require(isinstance(slots, list), "slots are required")
    expected = {(case_id, config_id, seed) for case_id in case_ids for config_id in config_ids for seed in seeds}
    observed: list[tuple[str, str, int]] = []
    for slot in slots:
        _require(isinstance(slot, dict), "slot must be an object")
        observed.append((slot.get("case_id"), slot.get("configuration_id"), slot.get("seed")))
    _require(len(observed) == len(set(observed)) and set(observed) == expected,
             "slots do not form the exact Cartesian case-by-configuration-by-seed set")
    return {"plan_id": plan_id, "expected_slots": len(expected), "review_families": len(set(entry["review_family_id"] for entry in cases))}


def validate_lock_set(plan: dict[str, Any], receipts: Iterable[dict[str, Any]]) -> dict[str, Any]:
    summary = validate_execution_plan(plan)
    expected = {(slot["case_id"], slot["configuration_id"], slot["seed"]) for slot in plan["slots"]}
    records = list(receipts)
    observed: set[tuple[str, str, int]] = set()
    for receipt in records:
        _require(isinstance(receipt, dict), "receipt must be an object")
        identity = (receipt.get("case_id"), receipt.get("configuration_id"), receipt.get("seed"))
        _require(identity not in observed, "duplicate locked receipt")
        observed.add(identity)
        _require(receipt.get("plan_id") == plan["plan_id"], "receipt plan binding mismatch")
        _require(receipt.get("status") in {"completed", "blocked", "abstained", "failed"}, "receipt is not terminal")
        _require(isinstance(receipt.get("output_sha256"), str) and _SHA256.fullmatch(receipt["output_sha256"]) is not None,
                 "receipt output hash is invalid")
    _require(observed == expected, "lock set incomplete or contains an unexpected slot")
    return {**summary, "locked_slots": len(observed), "lock_state": "complete"}


def unlock_reference(plan: dict[str, Any], receipts: Iterable[dict[str, Any]], case_id: str) -> dict[str, Any]:
    """Read one published reference only after every planned output is locked."""
    validate_lock_set(plan, receipts)
    entry = next((case for case in plan["cases"] if case["case_id"] == case_id), None)
    _require(entry is not None, f"unknown case_id: {case_id}")
    path = Path(entry["sealed_reference_path"])
    _require(path.is_file() and _sha256(path) == entry["sealed_reference_sha256"], "sealed reference hash drift")
    try:
        reference = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EndToEndReconstructionError("sealed reference is not valid UTF-8 JSON") from exc
    _require(isinstance(reference, dict), "sealed reference must be an object")
    return reference
