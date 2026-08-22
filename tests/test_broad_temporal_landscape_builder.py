from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.landscape_builder import (
    LandscapeBuildError,
    build_broad_temporal_landscape,
)
from metawingman.scripts.build_temporal_evidence_landscape import _read_jsonl


class BroadTemporalLandscapeBuilderTests(unittest.TestCase):
    def test_jsonl_reader_preserves_unicode_line_separator_inside_json_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "records.jsonl"
            path.write_text('{"id":"one","abstract":"left\u2028right"}\n', encoding="utf-8")
            self.assertEqual(_read_jsonl(path)[0]["abstract"], "left\u2028right")
    def setUp(self) -> None:
        self.spec = {
            "landscape_id": "mental-health-broad-2020",
            "run_context": "historical_rediscovery",
            "domain_ids": ["mental-health", "public-health"],
            "cutoff_date": "2020-06-07",
            "query_class": "broad_non_target_domain_query",
            "query_text": "mental health OR depression OR anxiety",
            "minimum_records": 2,
            "concepts": [
                {"node_id": "concept-depression", "node_type": "outcome", "label": "depression", "patterns": ["depress"]},
                {"node_id": "concept-anxiety", "node_type": "outcome", "label": "anxiety", "patterns": ["anxiety"]},
            ],
            "selection_policy": {
                "policy_version": "topic-policy-v1", "weights": {
                    "decision_relevance": 0.2, "unresolved_uncertainty": 0.15, "feasibility": 0.15,
                    "evidence_maturity": 0.1, "nonduplication": 0.15, "update_need": 0.1,
                    "equity_priority": 0.1, "cross_domain_value": 0.05
                },
                "minimum_primary_studies": 3, "minimum_source_families": 2,
                "minimum_known_item_recall": 0.8, "maximum_review_overlap": 0.6,
                "maximum_contamination_risk": 0.2, "maximum_ambiguity_risk": 0.3,
                "minimum_utility_score": 0.5, "maximum_portfolio_size": 3,
                "diversity_penalty": 0.1, "allow_update_topics": True
            }
        }
        self.records = [
            {"id": "pmid:1", "title": "Depression during a public health emergency", "abstract": "Symptoms varied.", "first_publication_date": "2020-05-01", "doi": "10.1/a", "source": "MED"},
            {"id": "pmid:2", "title": "Anxiety and population health", "abstract": "A cohort study.", "first_publication_date": "2020-05-20", "doi": "10.1/b", "source": "MED"},
        ]
        self.forbidden = ["secret target title", "10.9999/target"]

    def test_builds_verified_concept_edges_from_broad_records(self) -> None:
        result = build_broad_temporal_landscape(self.records, self.spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")
        self.assertEqual(result["build_audit"]["included_records"], 2)
        self.assertEqual(result["corpus_boundary"]["leakage_audit"], "passed")
        self.assertEqual(len([node for node in result["nodes"] if node["node_type"] == "publication"]), 2)
        self.assertEqual(len(result["edges"]), 2)
        self.assertNotIn("secret target title", str(result))

    def test_target_conditioned_query_fails_closed(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["query_class"] = "target_conditioned_query"
        with self.assertRaisesRegex(LandscapeBuildError, "broad non-target"):
            build_broad_temporal_landscape(self.records, spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")

    def test_identity_leak_or_postcutoff_record_fails_closed(self) -> None:
        leaked = copy.deepcopy(self.records)
        leaked[0]["title"] = "Secret target title"
        with self.assertRaisesRegex(LandscapeBuildError, "target identity leakage"):
            build_broad_temporal_landscape(leaked, self.spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")
        postcutoff = copy.deepcopy(self.records)
        postcutoff[0]["first_publication_date"] = "2020-06-08"
        with self.assertRaisesRegex(LandscapeBuildError, "post-cutoff"):
            build_broad_temporal_landscape(postcutoff, self.spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")

    def test_minimum_broad_landscape_size_is_enforced(self) -> None:
        with self.assertRaisesRegex(LandscapeBuildError, "minimum record floor"):
            build_broad_temporal_landscape(self.records[:1], self.spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")

    def test_uses_audited_conservative_date_for_non_iso_source_date(self) -> None:
        records = [copy.deepcopy(self.records[0])]
        records[0]["first_publication_date"] = "2020 May"
        records[0]["cutoff_verification"] = {
            "raw_publication_date": "2020 May",
            "conservative_latest_date": "2020-05-31",
            "cutoff": "2020-06-07",
            "status": "passed",
        }
        landscape = build_broad_temporal_landscape(
            records, {**self.spec, "minimum_records": 1}, self.forbidden,
            created_at_utc="2026-08-22T03:00:00Z",
        )
        publication = next(node for node in landscape["nodes"] if node["node_type"] == "publication")
        self.assertEqual(publication["observed_at"], "2020-05-31")

        records[0]["cutoff_verification"]["raw_publication_date"] = "spoofed"
        with self.assertRaisesRegex(LandscapeBuildError, "audited conservative"):
            build_broad_temporal_landscape(
                records, {**self.spec, "minimum_records": 1}, self.forbidden,
                created_at_utc="2026-08-22T03:00:00Z",
            )

    def test_corpus_derived_concepts_are_deterministic_and_forbid_target_terms(self) -> None:
        records = [
            {"id": f"pmid:{index}", "title": title, "abstract": abstract, "first_publication_date": "2020-05-01"}
            for index, (title, abstract) in enumerate([
                ("Walking programs for mood", "Physical activity and depressive symptoms"),
                ("Walking and mental health", "Physical activity supports mood outcomes"),
                ("Digital support for mood", "Remote care and depressive symptoms"),
                ("Digital mental health care", "Remote care and mood outcomes"),
            ], start=1)
        ]
        spec = copy.deepcopy(self.spec)
        spec["minimum_records"] = 4
        spec["concepts"] = []
        spec["concept_derivation"] = {
            "method": "corpus_ngram_document_frequency_v1",
            "maximum_concepts": 8,
            "minimum_document_frequency": 2,
        }
        first = build_broad_temporal_landscape(
            records, spec, [*self.forbidden, "secret intervention"],
            created_at_utc="2026-08-22T03:00:00Z",
        )
        second = build_broad_temporal_landscape(
            records, spec, [*self.forbidden, "secret intervention"],
            created_at_utc="2026-08-22T03:00:00Z",
        )
        concepts_first = [node for node in first["nodes"] if node["node_type"] == "concept"]
        concepts_second = [node for node in second["nodes"] if node["node_type"] == "concept"]
        self.assertEqual(concepts_first, concepts_second)
        self.assertTrue(any(node["label"] == "physical activity" for node in concepts_first))
        self.assertNotIn("secret intervention", str(concepts_first).casefold())

    def test_v2_corpus_concepts_filter_generic_abstract_language(self) -> None:
        records = [
            {"id": f"pmid:{index}", "title": title, "abstract": abstract, "first_publication_date": "2020-05-01"}
            for index, (title, abstract) in enumerate([
                ("Mobile media and sleep", "Children using portable media had shorter sleep duration"),
                ("Portable devices at bedtime", "Children using mobile devices had poor sleep quality"),
                ("Sleep habits in children", "Clinical patients had significant results after treatment"),
                ("Bedtime behavior", "Clinical patients had significant results using data"),
            ], start=1)
        ]
        spec = copy.deepcopy(self.spec)
        spec.update({"minimum_records": 4, "concepts": [], "concept_derivation": {
            "method": "corpus_ngram_document_frequency_v2", "maximum_concepts": 12,
            "minimum_document_frequency": 2,
        }})
        result = build_broad_temporal_landscape(records, spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")
        labels = [node["label"] for node in result["nodes"] if node["node_type"] == "concept"]
        self.assertTrue(any("portable" in label or "mobile" in label for label in labels))
        self.assertFalse(any(label in {"had", "significant", "results", "using", "patients"} for label in labels))

    def test_decision_opportunity_concepts_downweight_review_saturated_topics(self) -> None:
        records = []
        for index in range(1, 7):
            records.append({"id": f"p:{index}", "title": "Portable bedtime media and sleep", "abstract": "Mobile device access and poor sleep quality", "publication_types": ["Journal Article"], "first_publication_date": f"2020-0{index}-01"})
        for index in range(1, 7):
            records.append({"id": f"r:{index}", "title": "Systematic review of airway surgery", "abstract": "Airway surgery outcomes", "publication_types": ["Systematic Review"], "first_publication_date": f"2020-0{index}-01"})
        spec = copy.deepcopy(self.spec)
        spec.update({"minimum_records": 12, "concepts": [], "concept_derivation": {
            "method": "decision_opportunity_ngram_v1", "maximum_concepts": 8,
            "minimum_document_frequency": 2, "maximum_document_frequency": 20,
        }})
        result = build_broad_temporal_landscape(records, spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")
        labels = [node["label"] for node in result["nodes"] if node["node_type"] == "concept"]
        self.assertTrue(any("mobile device" in label or "portable bedtime" in label for label in labels))
        self.assertFalse(any(label == "airway surgery" for label in labels))

    def test_v2_decision_opportunity_reserves_unigram_and_bigram_capacity(self) -> None:
        records = [
            {"id": f"p:{index}", "title": "Mobile bedtime media", "abstract": "Portable device access predicts poor sleep quality", "publication_types": ["Journal Article"], "first_publication_date": "2020-05-01"}
            for index in range(1, 7)
        ]
        spec = copy.deepcopy(self.spec)
        spec.update({"minimum_records": 6, "concepts": [], "concept_derivation": {
            "method": "decision_opportunity_ngram_v2", "maximum_concepts": 6,
            "minimum_document_frequency": 2, "maximum_document_frequency": 20,
        }})
        result = build_broad_temporal_landscape(records, spec, self.forbidden, created_at_utc="2026-08-22T03:00:00Z")
        labels = [node["label"] for node in result["nodes"] if node["node_type"] == "concept"]
        self.assertTrue(any(" " not in label for label in labels))
        self.assertTrue(any(label.count(" ") == 1 for label in labels))


if __name__ == "__main__":
    unittest.main()
