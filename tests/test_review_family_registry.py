from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.review_family import (  # noqa: E402
    ReviewFamilyError,
    build_review_family_registry,
)
from metawingman_core.schema_guard import validate_document  # noqa: E402


TIMESTAMP = "2026-08-15T00:00:00Z"


def _record(identifier: str, title: str, year: int, authors: str, status: str = "development_candidate") -> dict:
    return {
        "record_id": f"epmc:MED:{identifier}",
        "title": title,
        "year": year,
        "authors": authors,
        "admission_status": status,
    }


class ReviewFamilyRegistryTests(unittest.TestCase):
    def test_conservative_candidates_are_never_confirmed_or_held_out_ready(self) -> None:
        corpus = {"records": [
            _record("1", "Exercise therapy for chronic low back pain: systematic review and meta-analysis", 2020, "Smith J, Doe A"),
            _record("2", "Updated exercise therapy for chronic low back pain: a systematic review and meta-analysis", 2024, "Smith J, Roe B"),
            _record("3", "Air pollution and childhood asthma: systematic review", 2023, "Chen L, Ray P"),
            _record("4", "Exercise therapy for chronic low back pain: systematic review and meta-analysis", 2021, "Smith J", "hold_integrity_review"),
        ]}
        registry = build_review_family_registry(
            corpus,
            source_path="fixture.json",
            generated_at_utc=TIMESTAMP,
        )
        validate_document(registry, "review_family_registry")
        self.assertEqual(registry["summary"]["records"], 4)
        self.assertEqual(registry["summary"]["held_out_ready_families"], 0)
        self.assertGreaterEqual(registry["summary"]["candidate_edges"], 2)
        linked = next(family for family in registry["families"] if len(family["record_ids"]) > 1)
        self.assertEqual(linked["status"], "blocked_integrity")
        self.assertEqual(linked["split_status"], "blocked_pending_family_audit")
        self.assertTrue(all(edge["status"] == "requires_audit" for edge in registry["candidate_edges"]))

    def test_non_reference_singleton_never_receives_a_split_suggestion(self) -> None:
        corpus = {"records": [
            _record(
                "1",
                "Response by Smith to a systematic review of alpha",
                2024,
                "Smith J",
                "exclude_non_reference",
            )
        ]}
        registry = build_review_family_registry(
            corpus,
            source_path="fixture.json",
            generated_at_utc=TIMESTAMP,
        )
        self.assertEqual(registry["families"][0]["status"], "excluded_non_reference")
        self.assertEqual(registry["families"][0]["suggested_split"], "not_applicable")

    def test_rejects_duplicate_record_ids(self) -> None:
        record = _record("1", "Review of alpha beta gamma delta", 2020, "Smith J")
        with self.assertRaisesRegex(ReviewFamilyError, "unique"):
            build_review_family_registry(
                {"records": [record, dict(record)]},
                source_path="fixture.json",
            )

    def test_boilerplate_reports_for_different_topics_do_not_chain(self) -> None:
        corpus = {"records": [
            _record(
                "1",
                "Screening for Ovarian Cancer: Updated Evidence Report and Systematic Review for the US Preventive Services Task Force",
                2023,
                "Agency Group",
            ),
            _record(
                "2",
                "Screening for Pancreatic Cancer: Updated Evidence Report and Systematic Review for the US Preventive Services Task Force",
                2023,
                "Agency Group",
            ),
        ]}
        registry = build_review_family_registry(
            corpus,
            source_path="fixture.json",
            generated_at_utc=TIMESTAMP,
        )
        self.assertEqual(registry["summary"]["candidate_edges"], 0)
        self.assertEqual(registry["summary"]["families"], 2)

    def test_committed_registry_covers_corpus_without_claiming_ready_split(self) -> None:
        corpus_path = ROOT / "research/top-journal-training-corpus.json"
        registry_path = ROOT / "research/top-journal-review-family-registry.json"
        if not registry_path.exists():
            self.skipTest("registry is generated after implementation tests")
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        validate_document(registry, "review_family_registry")
        member_ids = [
            identifier
            for family in registry["families"]
            for identifier in family["record_ids"]
        ]
        self.assertEqual(len(member_ids), len(corpus["records"]))
        self.assertEqual(set(member_ids), {record["record_id"] for record in corpus["records"]})
        self.assertEqual(registry["summary"]["held_out_ready_families"], 0)


if __name__ == "__main__":
    unittest.main()
