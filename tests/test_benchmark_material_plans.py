from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from fetch_benchmark_materials import (  # noqa: E402
    MaterialFetchError,
    fetch_plan,
    select_artifacts,
    validate_completed_run_boundary,
)
from metawingman_core.schema_guard import validate_document  # noqa: E402


PLAN_DIR = ROOT / "research/benchmark-material-plans"


def _load_plans() -> list[dict[str, object]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(PLAN_DIR.glob("*.json"))]


class BenchmarkMaterialPlanTests(unittest.TestCase):
    def test_priority_plans_validate_and_cover_five_families(self) -> None:
        plans = _load_plans()
        self.assertEqual(len(plans), 5)
        for plan in plans:
            validate_document(plan, "benchmark_material_plan")
        self.assertEqual(len({plan["review_family_id"] for plan in plans}), 5)

    def test_default_selection_never_exposes_answers(self) -> None:
        for plan in _load_plans():
            for artifact in select_artifacts(plan):
                self.assertIn(artifact["role"], {"operational_input", "documentation"})
                self.assertFalse(artifact["contains_answer"])

    def test_unlicensed_carbon_pack_fetches_nothing(self) -> None:
        plan = next(item for item in _load_plans() if item["pack_id"] == "carbon-pricing-screening")
        self.assertEqual(select_artifacts(plan), [])
        self.assertFalse(plan["license_assessment"]["pack_redistributable"])

    def test_fetch_verifies_bytes_hash_and_path(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            payload = b"immutable benchmark fixture\n"
            plan = {
                "schema_version": "1.0", "pack_id": "fixture-pack",
                "candidate_ids": ["fixture"], "review_family_id": "fixture-family",
                "supported_scopes": ["analysis"], "reproduction_ceiling": "analysis_only",
                "status": "development_ready", "historical_boundaries": [],
                "license_assessment": {"pack_redistributable": True, "reviewed_at_utc": "2026-08-13T00:00:00Z", "notes": "Test fixture."},
                "artifacts": [{
                    "artifact_id": "fixture", "role": "operational_input", "artifact_type": "other",
                    "source_url": "https://example.org/fixture.txt",
                    "immutable_revision": "fixture-v1", "destination": "fixture-pack/operational/fixture.txt",
                    "expected_sha256": hashlib.sha256(payload).hexdigest(), "expected_bytes": len(payload),
                    "license": {"status": "verified_open", "identifier": "MIT", "redistributable": True, "evidence_url": "https://example.org/license"},
                    "temporal_relation": "not_time_bound", "contains_answer": False,
                    "retrieval_policy": "fetch_by_default", "notes": ""
                }], "blockers": []
            }
            validate_document(plan, "benchmark_material_plan")
            response = io.BytesIO(payload)
            response.geturl = lambda: "https://example.org/fixture.txt"
            opener = unittest.mock.Mock()
            opener.open.return_value = response
            with (
                patch("fetch_benchmark_materials.validate_public_https_url", side_effect=lambda value: value),
                patch("fetch_benchmark_materials.public_https_opener", return_value=opener),
            ):
                result = fetch_plan(plan, Path(output_dir), max_bytes=1024)
            fetched = Path(output_dir) / "fixture-pack/operational/fixture.txt"
            self.assertEqual(fetched.read_bytes(), payload)
            self.assertEqual(result["artifacts"][0]["sha256"], hashlib.sha256(payload).hexdigest())

    def test_rejects_unsafe_default_and_destination(self) -> None:
        plan = next(
            item for item in _load_plans()
            if any(artifact["retrieval_policy"] == "fetch_by_default" for artifact in item["artifacts"])
        )
        bad = json.loads(json.dumps(plan))
        default_artifact = next(
            artifact for artifact in bad["artifacts"]
            if artifact["retrieval_policy"] == "fetch_by_default"
        )
        default_artifact["role"] = "sealed_reference"
        default_artifact["contains_answer"] = True
        with self.assertRaises(MaterialFetchError):
            select_artifacts(bad)

        unsafe = json.loads(json.dumps(plan))
        unsafe["artifacts"][0]["destination"] = "../escape.txt"
        with self.assertRaises(Exception):
            select_artifacts(unsafe)

    def test_private_network_source_is_rejected_before_fetch(self) -> None:
        plan = json.loads(json.dumps(_load_plans()[0]))
        artifact = plan["artifacts"][0]
        artifact["source_url"] = "https://127.0.0.1/private"
        artifact["retrieval_policy"] = "fetch_by_default"
        artifact["role"] = "operational_input"
        artifact["contains_answer"] = False
        artifact["expected_bytes"] = 1
        artifact["expected_sha256"] = hashlib.sha256(b"x").hexdigest()
        with tempfile.TemporaryDirectory() as output_dir:
            with self.assertRaises(Exception):
                fetch_plan(plan, Path(output_dir), max_bytes=1024)

    def test_sealed_unlock_requires_complete_valid_run_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boundary = root / "RUN_BOUNDARY.json"
            boundary.write_text("{}", encoding="utf-8")
            with self.assertRaises(MaterialFetchError):
                validate_completed_run_boundary(boundary, {"candidate_ids": ["fixture"]})
            lock = {
                "execution_mode": "ai_only",
                "configuration_id": "full",
                "repetition_index": 1,
                "human_interventions": 0,
                "operational_tree_sha256": "1" * 64,
                "output_sha256": "2" * 64,
                "prompt_sha256": "3" * 64,
                "model_versions": ["model@1"],
                "tool_versions": ["metawingman@1"],
            }
            boundary.write_text(json.dumps({
                "benchmark_id": "fixture", "run_state": "locked",
                "expected_runs": 1, "run_locks": [lock]
            }), encoding="utf-8")
            plan = {"candidate_ids": ["fixture"]}
            document = validate_completed_run_boundary(boundary, plan)
            self.assertEqual(document["run_state"], "locked")
            with self.assertRaises(MaterialFetchError):
                validate_completed_run_boundary(boundary, {"candidate_ids": ["another-case"]})
            with self.assertRaises(MaterialFetchError):
                fetch_plan({**plan, "schema_version": "1.0"}, root, unlock_sealed=True)


if __name__ == "__main__":
    unittest.main()
