from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.joint_lifecycle_runner import AtomicStageBudgetMeter
from metawingman.scripts.metawingman_core.joint_search_stage_adapter import search_retrieval_stage_adapter
from metawingman.scripts.metawingman_core.schema_guard import validate_document


ROOT = Path(__file__).resolve().parents[1]
TIMESTAMP = "2026-08-22T12:00:00Z"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _binding(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": _sha(path)}


class JointSearchStageAdapterTests(unittest.TestCase):
    def _fixture(self, root: Path, *, risk_control: bool) -> tuple[dict, list[str]]:
        prior_dir = root / "prior"
        prior_dir.mkdir()
        protocol = {
            "protocol_id": "protocol-case-1", "protocol_version": "1.0", "status": "frozen",
            "criteria_artifact": {"path": "unused", "schema": "protocol_criteria", "status": "frozen", "sha256": "a" * 64},
            "source_plan": [],
        }
        protocol_path = prior_dir / "protocol.json"
        _write(protocol_path, protocol)
        prior_manifest = {"stage_output": {"state_artifact_id": "protocol", "artifacts": [{
            "artifact_id": "protocol", "path": str(protocol_path), "sha256": _sha(protocol_path),
            "media_type": "application/json", "role": "stage_state",
        }]}}
        prior_path = prior_dir / "output-manifest.json"
        _write(prior_path, prior_manifest)
        calibration = {
            "schema_version": "1.0", "manifest_id": "calibration-1",
            "purpose": "operational_search_calibration_only", "target_reference_derived": False,
            "criteria": [{
                "criterion_id": "outcome-01", "critical": True,
                "downstream_claim_impact": 0.9, "hard_negative_error_rate": 0.01,
            }],
            "sentinels": [{
                "sentinel_id": "sentinel-a", "identifier_type": "pmid", "identifier": "101",
                "criterion_ids": ["outcome-01"],
            }],
        }
        calibration_path = root / "calibration.json"
        _write(calibration_path, calibration)
        sources = []
        protocol_sources = []
        for action_id, source_id, engine in (
            ("search-pubmed", "pubmed-main", "pubmed"),
            ("search-epmc", "epmc-second", "europe_pmc"),
        ):
            query_path = root / f"{source_id}.json"
            _write(query_path, {"query": "depression exercise", "cutoff_date": "2020-06-07"})
            sources.append({
                "action_id": action_id, "source_id": source_id, "source_family": source_id,
                "engine": engine, "maximum_records": 100,
                "target_criterion_ids": ["outcome-01"], "expected_risk_reduction": 0.8,
                "expected_claim_impact": 0.9, "estimated_cost_units": 1.0,
            })
            protocol_sources.append({
                "source_id": source_id, "query_file": query_path.relative_to(ROOT).as_posix(),
                "query_sha256": _sha(query_path),
            })
        protocol["source_plan"] = protocol_sources
        _write(protocol_path, protocol)
        prior_manifest["stage_output"]["artifacts"][0]["sha256"] = _sha(protocol_path)
        _write(prior_path, prior_manifest)
        config = {
            "schema_version": "1.0", "stage_id": "search_retrieval",
            "adapter_id": "joint-search-risk-impact-v1", "historical_cutoff": "2020-06-07",
            "calibration_manifest": _binding(calibration_path), "sources": sources,
            "fixed_action_count": 2,
            "thresholds": {
                "known_item_recall_floor": 1.0, "residual_omission_risk_ceiling": 0.05,
                "downstream_claim_impact_ceiling": 0.25, "hard_negative_error_ceiling": 0.05,
                "minimum_independent_sources": 1, "minimum_source_families": 1,
            },
            "loop_budget": {"max_actions": 2, "max_estimated_cost_units": 2.0, "max_wall_seconds": 30.0},
            "risk_formula_version": "observed-sentinel-source-coverage-v1",
        }
        validate_document(config, "joint_search_stage_config")
        output_dir = root / "search"
        output_dir.mkdir()
        request = {
            "case_id": "case-1", "arm_id": "risk" if risk_control else "generic", "seed": 20260820,
            "stage_id": "search_retrieval", "ordinal": 2, "repository_root": str(ROOT),
            "stage_output_dir": str(output_dir), "previous_output_manifest_path": str(prior_path),
            "previous_output_manifest_sha256": _sha(prior_path), "created_at_utc": TIMESTAMP,
            "config": config, "conclusion_risk_impact_control": risk_control,
            "acquisition_policy": "risk_impact_action_execute_replan" if risk_control else "fixed_generic",
            "published_reference_accessed": False,
        }
        calls: list[str] = []

        def searcher(source: dict, query: str, raw_dir: Path) -> tuple[list[dict], dict]:
            calls.append(source["source_id"])
            records = [{
                "record_id": f"{source['source_id']}:101", "source": source["source_id"],
                "pmid": "101", "doi": "", "pmcid": "", "nct_id": "",
                "title": "Eligible calibration study", "abstract": "Observed evidence.",
                "first_publication_date": "2020-06-01",
            }]
            if source["source_id"] == "epmc-second":
                records.append({
                    "record_id": "epmc:late", "source": source["source_id"], "pmid": "999",
                    "doi": "", "pmcid": "", "nct_id": "", "title": "Post-cutoff record",
                    "abstract": "Late.", "first_publication_date": "2020-06-08",
                })
            return records, {"source": source["source_id"], "reported_count": len(records), "retrieved_count": len(records)}

        request["_searcher"] = searcher
        return request, calls

    def test_risk_arm_executes_observed_action_recomputes_risk_and_stops(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            request, calls = self._fixture(Path(tmp), risk_control=True)
            output = search_retrieval_stage_adapter(
                request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 30})
            )
            validate_document(output, "joint_lifecycle_stage_output")
            self.assertEqual(calls, ["pubmed-main"])
            self.assertEqual(output["scientific_checks"][0]["check_id"], "risk_impact_action_execute_replan")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "search_state")
            state = json.loads(state_path.read_text())
            validate_document(state, "joint_search_stage_state")
            self.assertEqual(state["known_item_recall"], 1.0)
            self.assertTrue(state["risk_loop_result"]["full_risk_impact_controller_instantiated"])
            self.assertEqual(state["risk_loop_result"]["status"], "completed")

    def test_fixed_arm_runs_frozen_count_and_quarantines_postcutoff_records(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            request, calls = self._fixture(Path(tmp), risk_control=False)
            output = search_retrieval_stage_adapter(
                request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 30})
            )
            self.assertEqual(calls, ["pubmed-main", "epmc-second"])
            self.assertEqual(output["scientific_checks"][0]["check_id"], "fixed_acquisition")
            state_path = next(Path(x["path"]) for x in output["artifacts"] if x["artifact_id"] == "search_state")
            state = json.loads(state_path.read_text())
            self.assertEqual(len(state["records"]), 1)
            self.assertEqual(len(state["quarantined_records"]), 1)
            self.assertEqual(state["quarantined_records"][0]["temporal_gate"], "postcutoff")

    def test_target_derived_calibration_is_rejected_before_search(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            request, calls = self._fixture(Path(tmp), risk_control=True)
            binding = request["config"]["calibration_manifest"]
            path = ROOT / binding["path"]
            calibration = json.loads(path.read_text())
            calibration["target_reference_derived"] = True
            _write(path, calibration)
            request["config"]["calibration_manifest"]["sha256"] = _sha(path)
            with self.assertRaisesRegex(Exception, "target|const"):
                search_retrieval_stage_adapter(
                    request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 30})
                )
            self.assertEqual(calls, [])

    def test_fixed_and_adaptive_arms_must_share_the_same_action_ceiling(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            request, calls = self._fixture(Path(tmp), risk_control=False)
            request["config"]["fixed_action_count"] = 1
            with self.assertRaisesRegex(Exception, "same frozen action ceiling"):
                search_retrieval_stage_adapter(
                    request, AtomicStageBudgetMeter({"max_provider_calls": 0, "max_input_tokens": 0, "max_output_tokens": 0, "wall_seconds": 30})
                )
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
