from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from preflight_mainline import _run, _secret_findings, inspect_mainline_server


class ServerMainlinePreflightTests(unittest.TestCase):
    def test_hash_bound_coordinator_receipt_satisfies_provider_without_server_secret(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            roots = {name: root / name for name in ("src", "corpus", "cache", "runs", "checkpoints", "receipts")}
            for path in roots.values():
                path.mkdir()
            receipt = roots["receipts"] / "deepseek-capability.json"
            receipt.write_text(json.dumps({
                "schema_version": "1.0", "execution_state": "completed",
                "provider": "deepseek", "model": "deepseek-v4-flash",
                "execution_location": "coordinator", "observed_at_utc": "2026-08-20T12:00:00Z",
                "content_sha256": "a" * 64, "prompt_tokens": 36,
                "completion_tokens": 5, "total_tokens": 41,
            }), encoding="utf-8")
            config = {
                "source_root": str(roots["src"]), "corpus_root": str(roots["corpus"]),
                "cache_root": str(roots["cache"]), "run_root": str(roots["runs"]),
                "checkpoint_root": str(roots["checkpoints"]), "receipt_root": str(roots["receipts"]),
                "minimum_free_gib": 0, "minimum_gpu_memory_gib_each": 30,
                "expected_gpu_count": 1, "required_provider_model": "deepseek-v4-flash",
                "provider_capability_receipt": str(receipt),
                "expected_provider_capability_receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
            }
            report = inspect_mainline_server(config, inventory={
                "gpus": [{"name": "NVIDIA GeForce RTX 5090", "memory_total_mib": 32607}],
                "free_bytes_by_root": {str(path.resolve()): 10 * 1024**3 for path in roots.values()},
                "provider_capabilities": {"deepseek-v4-flash": False}, "packages": {},
            })
            self.assertTrue(report["ready"])
            self.assertEqual(report["provider_capability_source"], "coordinator_receipt")
            self.assertEqual(report["provider_capability_receipt_sha256"], config["expected_provider_capability_receipt_sha256"])

    def test_missing_executable_is_reported_not_raised(self) -> None:
        code, output = _run(["metawingman-command-that-does-not-exist"])
        self.assertEqual(code, 127)
        self.assertEqual(output, "")

    def test_secret_scan_ignores_explicit_test_fixture_but_catches_realistic_value(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fixture.py").write_text('api_key = "unit-test-secret"\n', encoding="utf-8")
            self.assertEqual(_secret_findings(root), [])
            (root / "unsafe.env").write_text('API_KEY="sk-live-A1b2C3d4E5f6G7h8I9j0"\n', encoding="utf-8")
            self.assertEqual(_secret_findings(root), ["unsafe.env"])
            self.assertEqual(_secret_findings(root, {"unsafe.env"}), [])

    def test_required_runtime_dependencies_block_ready(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            roots = {name: root / name for name in ("src", "corpus", "cache", "runs", "checkpoints", "receipts")}
            for path in roots.values():
                path.mkdir()
            config = {
                "source_root": str(roots["src"]), "corpus_root": str(roots["corpus"]),
                "cache_root": str(roots["cache"]), "run_root": str(roots["runs"]),
                "checkpoint_root": str(roots["checkpoints"]), "receipt_root": str(roots["receipts"]),
                "minimum_free_gib": 0, "minimum_gpu_memory_gib_each": 30,
                "expected_gpu_count": 1, "required_provider_model": "deepseek-v4-flash",
                "required_python_packages": ["torch", "scikit-learn"], "require_r": True,
            }
            report = inspect_mainline_server(config, inventory={
                "gpus": [{"name": "NVIDIA GeForce RTX 5090", "memory_total_mib": 32607}],
                "free_bytes_by_root": {str(path.resolve()): 10 * 1024**3 for path in roots.values()},
                "provider_capabilities": {"deepseek-v4-flash": True},
                "packages": {"torch": "2.13.0", "scikit-learn": None}, "r_version": None,
            })
            self.assertIn("required_python_package_missing:scikit-learn", report["blocking_findings"])
            self.assertIn("r_runtime_missing", report["blocking_findings"])

    def test_mainline_preflight_requires_separate_data_and_run_roots(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shared = root / "shared"
            shared.mkdir()
            config = {
                "schema_version": "1.0",
                "source_root": str(root / "src"),
                "corpus_root": str(shared),
                "cache_root": str(root / "cache"),
                "run_root": str(shared),
                "checkpoint_root": str(root / "checkpoints"),
                "receipt_root": str(root / "receipts"),
                "minimum_free_gib": 1,
                "minimum_gpu_memory_gib_each": 30,
                "expected_gpu_count": 1,
                "required_provider_model": "deepseek-v4-flash",
            }
            report = inspect_mainline_server(
                config,
                inventory={
                    "gpus": [{"name": "NVIDIA GeForce RTX 5090", "memory_total_mib": 32607}],
                    "free_bytes_by_root": {str(shared.resolve()): 10 * 1024**3},
                    "provider_capabilities": {"deepseek-v4-flash": True},
                },
            )
            self.assertFalse(report["ready"])
            self.assertIn("data_run_root_collision", report["blocking_findings"])

    def test_two_gpus_are_reported_individually_not_summed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            roots = {name: root / name for name in ("src", "corpus", "cache", "runs", "checkpoints", "receipts")}
            for path in roots.values():
                path.mkdir()
            config = {
                "schema_version": "1.0",
                "source_root": str(roots["src"]), "corpus_root": str(roots["corpus"]),
                "cache_root": str(roots["cache"]), "run_root": str(roots["runs"]),
                "checkpoint_root": str(roots["checkpoints"]), "receipt_root": str(roots["receipts"]),
                "minimum_free_gib": 0, "minimum_gpu_memory_gib_each": 40,
                "expected_gpu_count": 1, "required_provider_model": "deepseek-v4-flash",
            }
            report = inspect_mainline_server(
                config,
                inventory={
                    "gpus": [
                        {"name": "GPU A", "memory_total_mib": 24576},
                        {"name": "GPU B", "memory_total_mib": 24576},
                    ],
                    "free_bytes_by_root": {str(path.resolve()): 10 * 1024**3 for path in roots.values()},
                    "provider_capabilities": {"deepseek-v4-flash": True},
                },
            )
            self.assertIn("insufficient_per_gpu_memory", report["blocking_findings"])


if __name__ == "__main__":
    unittest.main()
