#!/usr/bin/env python3
"""Fail-closed MetaWingman server hardware, storage, source, and capability preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REQUIRED_ROOTS = ("source_root", "corpus_root", "cache_root", "run_root", "checkpoint_root", "receipt_root")
SECRET_PATTERNS = (
    re.compile(rb"(?i)(?:api[_-]?key|password|passwd|access[_-]?token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"),
    re.compile(rb"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
TEST_SECRET_MARKERS = (b"unit-test", b"test-only", b"dummy", b"not-a-real", b"example-secret")


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(argv, text=True, capture_output=True, timeout=20, check=False)
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, completed.stdout.strip()


def _gpu_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code, output = _run(["nvidia-smi", "--query-gpu=index,name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if code:
        return [], []
    gpus = []
    for line in output.splitlines():
        index, name, memory, driver = [item.strip() for item in line.split(",", 3)]
        gpus.append({"index": int(index), "name": name, "memory_total_mib": int(memory), "driver_version": driver})
    _, process_output = _run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"])
    processes = []
    for line in process_output.splitlines():
        if not line.strip():
            continue
        pid, name, memory = [item.strip() for item in line.split(",", 2)]
        processes.append({"pid": int(pid), "process_name": Path(name).name, "used_memory_mib": int(memory)})
    return gpus, processes


def _nearest_existing(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def collect_inventory(config: dict[str, Any]) -> dict[str, Any]:
    gpus, gpu_processes = _gpu_inventory()
    free = {}
    for name in REQUIRED_ROOTS:
        path = Path(config[name]).expanduser().resolve()
        free[str(path)] = shutil.disk_usage(_nearest_existing(path)).free
    package_names = ["jsonschema", "numpy", "scikit-learn", "torch", "transformers", "datasets", "accelerate", "PyMuPDF"]
    packages = {}
    for name in package_names:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    r_code, r_output = _run(["R", "--version"])
    return {
        "gpus": gpus,
        "active_gpu_processes": gpu_processes,
        "free_bytes_by_root": free,
        "cpu_count": os.cpu_count(),
        "ram_total_bytes": _ram_total_bytes(),
        "python_version": platform.python_version(),
        "r_version": r_output.splitlines()[0] if r_code == 0 and r_output else None,
        "packages": packages,
        "provider_capabilities": {config.get("required_provider_model", "deepseek-v4-flash"): bool(os.environ.get("DEEPSEEK_API_KEY"))},
    }


def _ram_total_bytes() -> int | None:
    path = Path("/proc/meminfo")
    if path.is_file():
        match = re.search(r"^MemTotal:\s+(\d+)\s+kB", path.read_text(encoding="utf-8"), re.MULTILINE)
        if match:
            return int(match.group(1)) * 1024
    return None


def _tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    excluded = {".git", "__pycache__", ".pytest_cache", "validation-output"}
    files = [item for item in root.rglob("*") if item.is_file() and not any(part in excluded for part in item.relative_to(root).parts)]
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big")); digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big")); digest.update(content)
    return digest.hexdigest()


def _verify_handoff(root: Path) -> tuple[bool, list[str]]:
    manifest_path = root / "server-training-handoff.json"
    if not manifest_path.is_file():
        return False, ["handoff_manifest_missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, ["handoff_manifest_invalid"]
    issues = []
    members = manifest.get("members", [])
    hashes = manifest.get("member_hashes", {})
    if set(members) != set(hashes):
        issues.append("handoff_hash_index_mismatch")
    for member in members:
        path = root / member
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes.get(member):
            issues.append(f"handoff_member_hash_drift:{member}")
    return not issues, issues


def _verify_provider_receipt(config: dict[str, Any], receipt_root: Path, required_model: str) -> tuple[bool, str | None]:
    value = str(config.get("provider_capability_receipt") or "").strip()
    expected_sha = str(config.get("expected_provider_capability_receipt_sha256") or "").strip()
    if not value or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        return False, None
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(receipt_root.resolve())
    except ValueError:
        return False, None
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        return False, None
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, None
    valid = (
        isinstance(receipt, dict)
        and receipt.get("schema_version") == "1.0"
        and receipt.get("execution_state") == "completed"
        and receipt.get("model") == required_model
        and receipt.get("execution_location") == "coordinator"
        and isinstance(receipt.get("provider"), str) and bool(receipt["provider"].strip())
        and isinstance(receipt.get("observed_at_utc"), str)
        and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", receipt["observed_at_utc"]))
        and isinstance(receipt.get("content_sha256"), str)
        and bool(re.fullmatch(r"[a-f0-9]{64}", receipt["content_sha256"]))
        and all(isinstance(receipt.get(key), int) and receipt[key] >= 0 for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
        and receipt["total_tokens"] == receipt["prompt_tokens"] + receipt["completion_tokens"]
    )
    return valid, expected_sha if valid else None


def _secret_findings(root: Path, allowlisted_paths: set[str] | None = None) -> list[str]:
    findings = []
    allowlisted = allowlisted_paths or set()
    excluded = {".git", "__pycache__", ".pytest_cache"}
    for path in sorted(item for item in root.rglob("*") if item.is_file() and not any(part in excluded for part in item.relative_to(root).parts)):
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".zip", ".pt", ".bin", ".safetensors"}:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        matches = [match.group(0).lower() for pattern in SECRET_PATTERNS for match in pattern.finditer(content)]
        relative = path.relative_to(root).as_posix()
        if relative not in allowlisted and any(not any(marker in match for marker in TEST_SECRET_MARKERS) for match in matches):
            findings.append(relative)
    return findings


def inspect_mainline_server(config: dict[str, Any], inventory: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[str] = []
    roots = {name: Path(str(config.get(name) or "")).expanduser().resolve() for name in REQUIRED_ROOTS}
    if any(not str(config.get(name) or "").strip() for name in REQUIRED_ROOTS):
        findings.append("required_root_missing")
    resolved = list(roots.values())
    if len(set(resolved)) != len(resolved):
        findings.append("data_run_root_collision")
    state = inventory or collect_inventory(config)
    minimum_free = float(config.get("minimum_free_gib", 100)) * 1024**3
    for path in resolved:
        available = state.get("free_bytes_by_root", {}).get(str(path))
        if available is None or int(available) < minimum_free:
            findings.append("insufficient_free_storage")
            break
    gpus = list(state.get("gpus") or [])
    if len(gpus) < int(config.get("expected_gpu_count", 1)):
        findings.append("insufficient_gpu_count")
    minimum_mib = float(config.get("minimum_gpu_memory_gib_each", 30)) * 1024
    if not gpus or max(int(item.get("memory_total_mib", 0)) for item in gpus) < minimum_mib:
        findings.append("insufficient_per_gpu_memory")
    if state.get("active_gpu_processes") and not config.get("allow_active_gpu_processes", False):
        findings.append("active_gpu_processes_present")
    packages = state.get("packages", {})
    for package in config.get("required_python_packages", []):
        if not packages.get(package):
            findings.append(f"required_python_package_missing:{package}")
    if config.get("require_r", False) and not state.get("r_version"):
        findings.append("r_runtime_missing")
    required_model = str(config.get("required_provider_model") or "deepseek-v4-flash")
    environment_capability = bool(state.get("provider_capabilities", {}).get(required_model, False))
    receipt_capability, provider_receipt_sha = _verify_provider_receipt(config, roots["receipt_root"], required_model)
    provider_capability = environment_capability or receipt_capability
    provider_source = "server_environment" if environment_capability else ("coordinator_receipt" if receipt_capability else None)
    if not provider_capability:
        findings.append("provider_capability_missing")
    source_root = roots["source_root"]
    source_sha = None
    if source_root.is_dir():
        source_sha = _tree_sha256(source_root)
        expected = config.get("expected_source_tree_sha256")
        if expected and source_sha != expected:
            findings.append("source_tree_hash_drift")
        secret_files = _secret_findings(source_root, set(config.get("secret_scan_allowlisted_paths", [])))
        if secret_files:
            findings.append("source_secret_scan_failed")
    elif inventory is None:
        findings.append("source_root_missing")
    handoff_root_value = config.get("handoff_root")
    handoff_ok = None
    handoff_issues: list[str] = []
    if handoff_root_value:
        handoff_ok, handoff_issues = _verify_handoff(Path(str(handoff_root_value)).resolve())
        findings.extend(handoff_issues)
    report = {
        "schema_version": "1.0",
        "ready": not findings,
        "blocking_findings": sorted(set(findings)),
        "gpu_count": len(gpus),
        "gpus": gpus,
        "active_gpu_processes": state.get("active_gpu_processes", []),
        "cpu_count": state.get("cpu_count"),
        "ram_total_bytes": state.get("ram_total_bytes"),
        "free_bytes_by_root": state.get("free_bytes_by_root", {}),
        "python_version": state.get("python_version"),
        "r_version": state.get("r_version"),
        "packages": state.get("packages", {}),
        "provider_capabilities": {required_model: provider_capability},
        "provider_capability_source": provider_source,
        "provider_capability_receipt_sha256": provider_receipt_sha,
        "source_tree_sha256": source_sha,
        "handoff_valid": handoff_ok,
        "handoff_findings": handoff_issues,
        "secret_scan_allowlisted_paths": list(config.get("secret_scan_allowlisted_paths", [])),
        "vram_aggregation_policy": "per_gpu_only_never_summed",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    report = inspect_mainline_server(config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
