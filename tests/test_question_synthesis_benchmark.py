from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "metawingman" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from metawingman_core.question_synthesis_evaluator import (
    QuestionSynthesisBenchmarkError,
    score_open_rubric,
    selective_curve,
    validate_benchmark_case,
    validate_family_isolation,
)


def benchmark_case_fixture() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "case_id": "case-1",
        "review_family_id": "family-development-1",
        "dependency_family_ids": ["dependency-development-1"],
        "graph_node_ids": ["graph-development-1"],
        "descendant_source_record_ids": ["record-development-1"],
        "cutoff_at_utc": "2024-01-01T00:00:00Z",
        "visible_material": [
            {
                "material_id": "visible-1",
                "filename": "visible-1.txt",
                "text": "Pre-cutoff clinical evidence.",
                "source_node_ids": ["graph-development-1"],
                "source_record_ids": ["record-development-1"],
                "observed_at_utc": "2023-12-01T00:00:00Z",
                "sha256": "277a8c59832d985cadb4ffd4d6d08cbb599b4f1d2daacd024c7370bc6ccc79fd",
            }
        ],
        "sealed_target": {"title": "Target review", "doi": "10.1000/target", "authors": ["Author A"]},
        "published_reference": {
            "review_family": "intervention",
            "synthesis_route": "pairwise_random_effects",
            "status": "verified_corrected_version",
            "verification": {
                "correction_or_corrigendum_handling": "No correction or corrigendum identified in the checked sources.",
                "retraction_check": "No retraction notice identified in the checked sources.",
                "protocol_version_audit": "Registry and publication version relationship checked.",
                "reproduction_ceiling": "Published aggregate results and reported methods only.",
                "verified_at_utc": "2026-08-20T00:00:00Z",
                "source_urls": ["https://example.org/reference-audit"],
            },
        },
        "leakage_patterns": ["10.1000/target", "Target review"],
        "loss_rubric": {"correct": 1.0, "abstain": 0.4, "critical_error": -2.0},
        "split": "development",
        "status": "sealed",
    }


def rehash_visible_item(item: dict[str, object]) -> None:
    item["sha256"] = hashlib.sha256(str(item["text"]).encode("utf-8")).hexdigest()


def isolated_case(split: str, suffix: str) -> dict[str, object]:
    case = copy.deepcopy(benchmark_case_fixture())
    case["case_id"] = f"case-{suffix}"
    case["review_family_id"] = f"family-{suffix}"
    case["dependency_family_ids"] = [f"dependency-{suffix}"]
    case["graph_node_ids"] = [f"graph-{suffix}"]
    case["descendant_source_record_ids"] = [f"record-{suffix}"]
    case["split"] = split
    material = case["visible_material"][0]
    material["source_node_ids"] = [f"graph-{suffix}"]
    material["source_record_ids"] = [f"record-{suffix}"]
    return case


class QuestionSynthesisBenchmarkTests(unittest.TestCase):
    def test_case_rejects_target_identifier_in_visible_material(self) -> None:
        case = benchmark_case_fixture()
        case["visible_material"][0]["text"] += " " + case["sealed_target"]["doi"]
        rehash_visible_item(case["visible_material"][0])
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_rejects_visible_material_hash_mismatch(self) -> None:
        case = benchmark_case_fixture()
        case["visible_material"][0]["sha256"] = "0" * 64
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_rejects_leak_only_in_visible_filename(self) -> None:
        case = benchmark_case_fixture()
        case["visible_material"][0]["filename"] = "Target review.txt"
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_rejects_leak_only_in_graph_or_source_reference(self) -> None:
        mutations = (
            ("graph_node_ids", "source_node_ids"),
            ("descendant_source_record_ids", "source_record_ids"),
        )
        for closure_field, material_field in mutations:
            with self.subTest(closure_field=closure_field, material_field=material_field):
                case = benchmark_case_fixture()
                case[closure_field] = ["Target review"]
                case["visible_material"][0][material_field] = ["Target review"]
                with self.assertRaisesRegex(
                    QuestionSynthesisBenchmarkError,
                    "sealed target identity appears in visible material",
                ):
                    validate_benchmark_case(case)

    def test_case_rejects_optional_sealed_identifier_in_visible_metadata(self) -> None:
        case = benchmark_case_fixture()
        case["sealed_target"]["identifiers"] = ["PMID:12345"]
        case["visible_material"][0]["material_id"] = "source-PMID:12345"
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_does_not_treat_json_field_names_as_visible_values(self) -> None:
        case = benchmark_case_fixture()
        case["leakage_patterns"] = ["material_id"]
        try:
            validate_benchmark_case(case)
        except QuestionSynthesisBenchmarkError as exc:
            self.fail(f"field-name-only match was treated as visible leakage: {exc}")

    def test_case_rejects_post_cutoff_visible_material(self) -> None:
        case = benchmark_case_fixture()
        case["visible_material"][0]["observed_at_utc"] = "2024-01-02T00:00:00Z"
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_rejects_visible_source_reference_outside_declared_closure(self) -> None:
        case = benchmark_case_fixture()
        case["visible_material"][0]["source_node_ids"] = ["undeclared-graph-node"]
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_benchmark_case(case)

    def test_case_rejects_empty_graph_and_source_arrays(self) -> None:
        mutations = (
            ("graph_node_ids", "source_node_ids", True),
            ("descendant_source_record_ids", "source_record_ids", True),
            (None, "source_node_ids", False),
            (None, "source_record_ids", False),
        )
        for closure_field, material_field, empty_closure in mutations:
            with self.subTest(closure_field=closure_field, material_field=material_field):
                case = benchmark_case_fixture()
                if empty_closure:
                    case[closure_field] = []
                case["visible_material"][0][material_field] = []
                with self.assertRaisesRegex(QuestionSynthesisBenchmarkError, "validation failed"):
                    validate_benchmark_case(case)

    def test_case_rejects_whitespace_only_critical_identifiers(self) -> None:
        mutations = (
            ("review_family_id", None),
            ("dependency_family_ids", None),
            ("graph_node_ids", "source_node_ids"),
            ("descendant_source_record_ids", "source_record_ids"),
            ("material_id", None),
            ("filename", None),
            ("source_node_ids", "graph_node_ids"),
            ("source_record_ids", "descendant_source_record_ids"),
        )
        for field, related_field in mutations:
            with self.subTest(field=field):
                case = benchmark_case_fixture()
                if field in {"material_id", "filename"}:
                    case["visible_material"][0][field] = " "
                elif field in {"source_node_ids", "source_record_ids"}:
                    case[field if related_field is None else related_field] = [" "]
                    case["visible_material"][0][field] = [" "]
                else:
                    case[field] = " " if field == "review_family_id" else [" "]
                    if related_field is not None:
                        case["visible_material"][0][related_field] = [" "]
                with self.assertRaisesRegex(QuestionSynthesisBenchmarkError, "validation failed"):
                    validate_benchmark_case(case)

    def test_case_accepts_empty_dependency_family_ids(self) -> None:
        case = benchmark_case_fixture()
        case["dependency_family_ids"] = []
        validate_benchmark_case(case)

    def test_case_rejects_whitespace_only_sealed_target_identity(self) -> None:
        mutations = (
            ("title", " "),
            ("doi", " "),
            ("authors", [" "]),
            ("identifiers", [" "]),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                case = benchmark_case_fixture()
                case["sealed_target"][field] = value
                with self.assertRaisesRegex(QuestionSynthesisBenchmarkError, "validation failed"):
                    validate_benchmark_case(case)

    def test_case_rejects_whitespace_only_published_reference_labels(self) -> None:
        for field in ("review_family", "synthesis_route"):
            with self.subTest(field=field):
                case = benchmark_case_fixture()
                case["published_reference"][field] = " "
                with self.assertRaisesRegex(QuestionSynthesisBenchmarkError, "validation failed"):
                    validate_benchmark_case(case)

    def test_case_rejects_incomplete_published_reference_verification(self) -> None:
        required_fields = (
            "correction_or_corrigendum_handling",
            "retraction_check",
            "protocol_version_audit",
            "reproduction_ceiling",
            "verified_at_utc",
            "source_urls",
        )
        for field in required_fields:
            with self.subTest(field=field):
                case = benchmark_case_fixture()
                del case["published_reference"]["verification"][field]
                with self.assertRaises(QuestionSynthesisBenchmarkError):
                    validate_benchmark_case(case)

    def test_development_and_calibration_cannot_share_dependency(self) -> None:
        development = isolated_case("development", "development-a")
        calibration = isolated_case("calibration", "calibration-a")
        calibration["dependency_family_ids"] = [development["dependency_family_ids"][0]]
        with self.assertRaises(QuestionSynthesisBenchmarkError):
            validate_family_isolation([development, calibration])

    def test_calibration_and_held_out_cannot_share_graph_or_descendant(self) -> None:
        mutations = (
            ("graph_node_ids", "source_node_ids"),
            ("descendant_source_record_ids", "source_record_ids"),
        )
        for closure_field, material_field in mutations:
            with self.subTest(closure_field=closure_field):
                calibration = isolated_case("calibration", f"calibration-{closure_field}")
                held_out = isolated_case("held_out", f"held-out-{closure_field}")
                shared_identifier = calibration[closure_field][0]
                held_out[closure_field] = [shared_identifier]
                held_out["visible_material"][0][material_field] = [shared_identifier]
                with self.assertRaisesRegex(
                    QuestionSynthesisBenchmarkError,
                    "family/dependency closure crosses benchmark splits",
                ):
                    validate_family_isolation([calibration, held_out])

    def test_family_isolation_rejects_duplicate_case_id(self) -> None:
        development = isolated_case("development", "development-duplicate")
        calibration = isolated_case("calibration", "calibration-duplicate")
        calibration["case_id"] = development["case_id"]
        with self.assertRaisesRegex(QuestionSynthesisBenchmarkError, "duplicate benchmark case_id"):
            validate_family_isolation([development, calibration])

    def test_family_isolation_accepts_disjoint_splits_and_same_split_sharing(self) -> None:
        development_a = isolated_case("development", "development-a")
        development_b = isolated_case("development", "development-b")
        development_b["dependency_family_ids"] = development_a["dependency_family_ids"].copy()
        cases = [
            development_a,
            development_b,
            isolated_case("calibration", "calibration-a"),
            isolated_case("held_out", "held-out-a"),
            isolated_case("prospective", "prospective-a"),
        ]
        validate_family_isolation(cases)

    def test_critical_error_scores_below_abstention(self) -> None:
        rubric = {"correct": 1.0, "abstain": 0.4, "critical_error": -2.0}
        self.assertLess(score_open_rubric("critical_error", rubric), score_open_rubric("abstain", rubric))

    def test_selective_curve_orders_by_confidence_then_case(self) -> None:
        curve = selective_curve([
            {"case_id": "b", "confidence": 0.5, "loss": 1.0},
            {"case_id": "a", "confidence": 0.9, "loss": 0.0},
        ])
        self.assertEqual(curve[0]["coverage"], 0.5)
        self.assertEqual(curve[0]["risk"], 0.0)


if __name__ == "__main__":
    unittest.main()
