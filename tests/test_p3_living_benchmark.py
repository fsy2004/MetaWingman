from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "metawingman" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.benchmark_packager import (  # noqa: E402
    BenchmarkPackageError,
    build_benchmark_package,
    lock_benchmark_run,
)
from metawingman_core.living_update import (  # noqa: E402
    LivingUpdateError,
    build_domain_state_snapshot,
    build_snapshot,
    compare_snapshots,
    plan_living_update,
)
from metawingman_core.biomedical_domain import load_domain_packs  # noqa: E402
from metawingman_core.provenance_graph import ProvenanceGraph  # noqa: E402


TIMESTAMP = "2026-08-13T00:00:00Z"
QUERY_HASH = "a" * 64
PACK_DIR = REPO_ROOT / "metawingman/references/domain-packs"


def node(node_type: str, node_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0", "node_type": node_type, "node_id": node_id,
        "label": node_id, "status": "accepted", "artifact_ref": None,
        "payload_sha256": None,
        "created_by": {"type": "tool", "id": "fixture", "version": "1.0"},
        "created_at_utc": TIMESTAMP,
    }


def edge(edge_id: str, source: tuple[str, str], target: tuple[str, str], relationship: str) -> dict[str, object]:
    return {
        "schema_version": "1.0", "edge_id": edge_id,
        "from_node": {"type": source[0], "id": source[1]},
        "to_node": {"type": target[0], "id": target[1]},
        "relationship": relationship, "evidence_refs": ["fixture"], "status": "accepted",
        "created_by": {"type": "tool", "id": "fixture", "version": "1.0"},
        "verification": {
            "status": "passed", "verified_by": "fixture",
            "verified_at_utc": TIMESTAMP, "notes": "Synthetic lineage fixture.",
        },
        "created_at_utc": TIMESTAMP,
    }


def record(
    canonical_id: str,
    metadata_hash: str,
    *,
    status: str = "active",
    provenance_node: dict[str, str] | None = None,
) -> dict[str, object]:
    return {
        "record_id": f"record:{canonical_id}", "canonical_id": canonical_id,
        "source_record_id": canonical_id, "metadata_sha256": metadata_hash,
        "status": status, "version": "1", "published_at": "2026-01-01",
        "provenance_node": provenance_node,
    }


def snapshot(snapshot_id: str, records: list[dict[str, object]]) -> dict[str, object]:
    return build_snapshot({
        "snapshot_id": snapshot_id, "project_id": "project-1", "source_id": "pubmed",
        "query_sha256": QUERY_HASH, "search_completed_at_utc": TIMESTAMP,
        "source_data_timestamp": "2026-08-13", "records": records,
    })


def snapshot_with_pack_hash(pack_hash: str) -> dict[str, object]:
    return {
        "domain_pack_hash": pack_hash,
        "terminology_releases": [],
        "affected_evidence": ["report:report-1"],
        "affected_claims": ["claim:claim-1"],
    }


def benchmark_candidate(
    protocol: Path,
    published_review: Path,
    post_cutoff: Path,
    *,
    visibility: str = "private",
    published_redistributable: bool = False,
) -> dict[str, object]:
    return {
        "benchmark_id": "benchmark-1", "benchmark_version": "0.1.0",
        "visibility": visibility,
        "review": {
            "review_id": "review-1", "title": "Published review reconstruction",
            "doi": "10.0000/example", "publication_date": "2024-06-01",
            "review_family": "intervention", "review_family_id": "family-1",
        },
        "reconstruction": {"search_cutoff_date": "2023-12-31"},
        "split": {
            "name": "test", "unit": "review_family_id",
            "assignment_basis": "Held out by review family before prompt optimization.",
        },
        "artifacts": [
            {
                "artifact_id": "protocol", "path": str(protocol), "role": "operational_input",
                "artifact_type": "protocol", "destination": "protocol/protocol.txt",
                "source": "Published protocol", "license": "CC BY 4.0",
                "redistributable": True, "available_at_cutoff": True,
                "contains_answer": False, "notes": "Available before cutoff.",
            },
            {
                "artifact_id": "published-review", "path": str(published_review),
                "role": "sealed_reference", "artifact_type": "published_review",
                "destination": "reference/published-review.txt", "source": "Journal article",
                "license": "User-accessed for private validation",
                "redistributable": published_redistributable, "available_at_cutoff": False,
                "contains_answer": True, "notes": "Sealed until run lock.",
            },
            {
                "artifact_id": "post-cutoff-study", "path": str(post_cutoff),
                "role": "operational_input", "artifact_type": "source_report",
                "destination": "post-cutoff/study.txt", "source": "Public report",
                "license": "CC BY 4.0", "redistributable": True,
                "available_at_cutoff": False, "available_date": "2025-01-01",
                "contains_answer": False, "notes": "Must not leak into reconstruction.",
            },
        ],
        "evaluation_design": {
            "design": "ai_only_repeated_runs",
            "configuration_ids": ["full"],
            "repetitions_per_configuration": 2,
        },
        "created_at_utc": TIMESTAMP,
    }


class LivingUpdateTests(unittest.TestCase):
    def test_domain_state_snapshot_records_active_pack_versions_terms_and_hashes(self) -> None:
        value = build_domain_state_snapshot(
            load_domain_packs(PACK_DIR),
            snapshot_id="domain-state-1",
            affected_evidence=["report:report-1"],
            affected_claims=["claim:claim-1"],
        )
        self.assertEqual(len(value["active_packs"]), 6)
        self.assertEqual(
            {"pack_id", "version", "content_sha256"},
            set(value["active_packs"][0]),
        )
        self.assertEqual(value["terminology_releases"], [])
        self.assertEqual(len(value["domain_state_sha256"]), 64)

    def test_domain_pack_drift_requires_explicit_living_migration(self) -> None:
        result = plan_living_update(
            snapshot_with_pack_hash("1" * 64),
            current_pack_hash="2" * 64,
        )
        self.assertEqual(result["status"], "blocked_pending_domain_migration")
        self.assertIn("domain_pack_hash_changed", result["reason_codes"])
        self.assertEqual(result["affected_evidence"], ["report:report-1"])
        self.assertEqual(result["affected_claims"], ["claim:claim-1"])

    def test_terminology_drift_requires_explicit_living_migration(self) -> None:
        previous = snapshot_with_pack_hash("1" * 64)
        previous["terminology_releases"] = [{
            "pack_id": "biomedical-foundation",
            "system": "SNOMED CT",
            "release": "2026-01-01",
            "content_sha256": "3" * 64,
        }]
        result = plan_living_update(
            previous,
            current_pack_hash="1" * 64,
            current_terminology_releases=[{
                "pack_id": "biomedical-foundation",
                "system": "SNOMED CT",
                "release": "2026-07-01",
                "content_sha256": "4" * 64,
            }],
        )
        self.assertEqual(result["status"], "blocked_pending_domain_migration")
        self.assertIn("terminology_release_changed", result["reason_codes"])

    def test_only_explicit_non_model_migration_event_clears_domain_drift(self) -> None:
        previous = snapshot_with_pack_hash("1" * 64)
        model_result = plan_living_update(
            previous,
            current_pack_hash="2" * 64,
            migration_event={
                "event_type": "domain_migration",
                "actor_type": "model",
                "approved": True,
                "from_domain_state_sha256": "1" * 64,
                "to_domain_state_sha256": "2" * 64,
            },
        )
        self.assertEqual(model_result["status"], "blocked_pending_domain_migration")
        self.assertIn(
            "model_response_cannot_authorize_domain_migration",
            model_result["reason_codes"],
        )

        migrated = plan_living_update(
            previous,
            current_pack_hash="2" * 64,
            migration_event={
                "event_type": "domain_migration",
                "actor_type": "human",
                "approved": True,
                "from_domain_state_sha256": "1" * 64,
                "to_domain_state_sha256": "2" * 64,
            },
        )
        self.assertEqual(migrated["status"], "ready_after_domain_migration")
        self.assertFalse(migrated["migration_required"])

    def test_snapshot_hash_detects_tampering(self) -> None:
        value = snapshot("snapshot-1", [record("doi:1", "1" * 64)])
        value["records"][0]["status"] = "retracted"
        with self.assertRaises(LivingUpdateError):
            compare_snapshots(value, snapshot("snapshot-2", []), delta_id="delta-1")

    def test_new_and_status_changed_records_create_human_actions(self) -> None:
        previous = snapshot("snapshot-1", [record("doi:1", "1" * 64)])
        current = snapshot("snapshot-2", [
            record("doi:1", "2" * 64, status="retracted"),
            record("doi:2", "3" * 64),
        ])
        delta = compare_snapshots(previous, current, delta_id="delta-1", created_at_utc=TIMESTAMP)
        self.assertEqual({item["change_type"] for item in delta["changes"]}, {"status_changed", "new"})
        self.assertIn("screen_new_records", delta["required_actions"])
        self.assertIn("recheck_report_identity", delta["required_actions"])
        self.assertEqual(delta["status"], "ready_for_human")

    def test_graph_impact_reaches_analysis_and_claim(self) -> None:
        previous = snapshot("snapshot-1", [
            record("doi:1", "1" * 64, provenance_node={"type": "report", "id": "report-1"})
        ])
        current = snapshot("snapshot-2", [
            record("doi:1", "2" * 64, status="corrected", provenance_node={"type": "report", "id": "report-1"})
        ])
        with tempfile.TemporaryDirectory() as directory:
            with ProvenanceGraph(Path(directory) / "graph.sqlite3") as graph:
                for graph_node in (
                    node("report", "report-1"), node("study", "study-1"),
                    node("result", "result-1"), node("synthesis", "synthesis-1"),
                    node("analysis", "analysis-1"), node("claim", "claim-1"),
                ):
                    graph.add_node(graph_node)
                for graph_edge in (
                    edge("edge-1", ("report", "report-1"), ("study", "study-1"), "is_report_of"),
                    edge("edge-2", ("study", "study-1"), ("result", "result-1"), "reports_result"),
                    edge("edge-3", ("result", "result-1"), ("synthesis", "synthesis-1"), "included_in_synthesis"),
                    edge("edge-4", ("synthesis", "synthesis-1"), ("analysis", "analysis-1"), "analyzed_by"),
                    edge("edge-5", ("analysis", "analysis-1"), ("claim", "claim-1"), "supports_claim"),
                ):
                    graph.add_edge(graph_edge)
                delta = compare_snapshots(
                    previous, current, delta_id="delta-1", graph=graph,
                    created_at_utc=TIMESTAMP,
                )
        self.assertEqual(delta["impact"][0]["impact_status"], "downstream_nodes_found")
        self.assertIn("rerun_analysis", delta["required_actions"])
        self.assertIn("recompile_claims", delta["required_actions"])


class BenchmarkPackageTests(unittest.TestCase):
    def _sources(self, root: Path) -> tuple[Path, Path, Path]:
        sources = root / "sources"
        sources.mkdir()
        protocol = sources / "protocol.txt"
        review = sources / "published-review.txt"
        post = sources / "post-cutoff.txt"
        protocol.write_text("Protocol available before cutoff.", encoding="utf-8")
        review.write_text("Included studies and pooled result answer.", encoding="utf-8")
        post.write_text("Study published after cutoff.", encoding="utf-8")
        return protocol, review, post

    def test_package_physically_separates_answers_and_post_cutoff_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = self._sources(root)
            package = root / "package"
            manifest = build_benchmark_package(benchmark_candidate(*sources), package)
            roles = {item["artifact_id"]: item["role"] for item in manifest["artifacts"]}
            self.assertEqual(roles["protocol"], "operational_input")
            self.assertEqual(roles["published-review"], "sealed_reference")
            self.assertEqual(roles["post-cutoff-study"], "sealed_post_cutoff")
            self.assertTrue((package / "operational/protocol/protocol.txt").is_file())
            self.assertTrue((package / "sealed/reference/published-review.txt").is_file())
            self.assertFalse((package / "operational/post-cutoff/study.txt").exists())

    def test_public_package_rejects_nonredistributable_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = self._sources(root)
            with self.assertRaises(BenchmarkPackageError):
                build_benchmark_package(
                    benchmark_candidate(*sources, visibility="public", published_redistributable=False),
                    root / "package",
                )

    def test_package_rejects_embedded_secret_and_sensitive_file_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protocol, review, post = self._sources(root)
            protocol.write_text("api_key=abcdefghijklmnop", encoding="utf-8")
            with self.assertRaises(BenchmarkPackageError):
                build_benchmark_package(
                    benchmark_candidate(protocol, review, post), root / "secret-package"
                )
            protocol.write_text("ordinary content", encoding="utf-8")
            sensitive = protocol.with_suffix(".pem")
            protocol.rename(sensitive)
            with self.assertRaises(BenchmarkPackageError):
                build_benchmark_package(
                    benchmark_candidate(sensitive, review, post), root / "sensitive-package"
                )

    def test_run_lock_records_output_before_unsealing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = self._sources(root)
            package = root / "package"
            build_benchmark_package(benchmark_candidate(*sources), package)
            run_output = root / "run-output.json"
            run_output.write_text(json.dumps({"screening": []}), encoding="utf-8")
            first = lock_benchmark_run(package, {
                "run_id": "run-1", "execution_mode": "ai_only",
                "configuration_id": "full", "repetition_index": 1,
                "model_versions": ["fixture-model@1"], "prompt_sha256": "9" * 64,
                "tool_versions": ["metawingman@0.1"], "output_path": str(run_output),
                "human_interventions": 0, "wall_clock_seconds": 12.5,
                "model_calls": 4, "input_tokens": 1000, "output_tokens": 200,
                "api_cost": 0.04, "compute_cost": 0.01, "cost_currency": "USD",
            }, created_at_utc=TIMESTAMP)
            self.assertEqual(first["run_state"], "collecting")
            boundary = lock_benchmark_run(package, {
                "run_id": "run-2", "execution_mode": "ai_only",
                "configuration_id": "full", "repetition_index": 2,
                "model_versions": ["fixture-model@1"], "prompt_sha256": "9" * 64,
                "tool_versions": ["metawingman@0.1"], "output_path": str(run_output),
                "human_interventions": 0, "wall_clock_seconds": 11.0,
                "model_calls": 4, "input_tokens": 900, "output_tokens": 180,
                "api_cost": 0.035, "compute_cost": 0.01, "cost_currency": "USD",
            }, created_at_utc=TIMESTAMP)
            self.assertEqual(boundary["run_state"], "locked")
            self.assertEqual(len(boundary["run_locks"]), 2)
            self.assertEqual(boundary["run_locks"][0]["output_sha256"], __import__("hashlib").sha256(run_output.read_bytes()).hexdigest())

    def test_legacy_human_comparison_arms_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = benchmark_candidate(*self._sources(root))
            candidate["comparison_arms"] = ["human_only", "ai_only"]
            with self.assertRaises(BenchmarkPackageError):
                build_benchmark_package(candidate, root / "package")

    def test_ai_only_run_rejects_human_intervention(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            build_benchmark_package(benchmark_candidate(*self._sources(root)), package)
            run_output = root / "run-output.json"
            run_output.write_text("{}", encoding="utf-8")
            run = {
                "run_id": "run-1", "execution_mode": "ai_only",
                "configuration_id": "full", "repetition_index": 1,
                "model_versions": ["fixture-model@1"], "prompt_sha256": "9" * 64,
                "tool_versions": ["metawingman@0.1"], "output_path": str(run_output),
                "human_interventions": 1, "wall_clock_seconds": 1.0,
                "model_calls": 1, "input_tokens": 10, "output_tokens": 5,
                "api_cost": 0.0, "compute_cost": 0.0, "cost_currency": "USD",
            }
            with self.assertRaises(BenchmarkPackageError):
                lock_benchmark_run(package, run, created_at_utc=TIMESTAMP)


if __name__ == "__main__":
    unittest.main()
