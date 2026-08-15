from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from harvest_top_journal_corpus import _record, harvest  # noqa: E402


class TopJournalCorpusTests(unittest.TestCase):
    def test_title_contamination_routes_notices_and_comments(self) -> None:
        base = {
            "source": "MED", "pubYear": "2025",
            "journalInfo": {"journal": {"title": "Journal A"}},
        }
        comment = _record({
            **base,
            "id": "comment",
            "title": "Comments regarding 'A systematic review and meta-analysis of alpha'.",
            "pubTypeList": {"pubType": ["Comment", "Letter"]},
        }, "top_general")
        correction = _record({
            **base,
            "id": "correction",
            "title": "Correction: A systematic review and meta-analysis of alpha.",
        }, "top_general")
        retraction = _record({
            **base,
            "id": "retraction",
            "title": "Retraction notice to A systematic review and meta-analysis of alpha.",
        }, "top_general")
        self.assertEqual(comment["admission_status"], "exclude_non_reference")
        self.assertEqual(correction["admission_status"], "hold_integrity_review")
        self.assertEqual(retraction["admission_status"], "exclude_retracted")

        response = _record({
            **base,
            "id": "response",
            "title": "Response by Smith to Letter Regarding Article, 'A meta-analysis of alpha'.",
            "pubTypeList": {"pubType": ["Letter"]},
        }, "top_general")
        recommendation = _record({
            **base,
            "id": "guideline",
            "title": "Screening for Alpha: Recommendation Statement.",
            "pubTypeList": {"pubType": ["Practice Guideline", "Systematic Review"]},
        }, "top_general")
        self.assertEqual(response["admission_status"], "exclude_non_reference")
        self.assertEqual(recommendation["admission_status"], "exclude_non_reference")

    def test_harvest_deduplicates_and_routes_integrity_updates(self) -> None:
        responses = [
            {
                "version": "6.9",
                "hitCount": 2,
                "resultList": {"result": [
                    {
                        "source": "MED", "id": "1", "pmid": "1", "doi": "10.1/test",
                        "title": "Systematic review and meta-analysis of alpha", "authorString": "A",
                        "pubYear": "2024", "journalInfo": {"journal": {"title": "Journal A"}},
                        "pubTypeList": {"pubType": ["Systematic Review"]}, "isOpenAccess": "Y",
                        "license": "cc by", "citedByCount": 7,
                    },
                    {
                        "source": "MED", "id": "2", "pmid": "2", "doi": "10.1/retracted",
                        "title": "Meta-analysis of beta", "authorString": "B", "pubYear": "2023",
                        "journalInfo": {"journal": {"title": "Journal A"}},
                        "pubTypeList": {"pubType": ["Meta-Analysis"]},
                        "commentCorrectionList": {"commentCorrection": [{"type": "Retraction in"}]},
                    },
                ]},
            },
            {
                "version": "6.9", "hitCount": 1,
                "resultList": {"result": [{
                    "source": "MED", "id": "1", "pmid": "1", "doi": "10.1/test",
                    "title": "Systematic review and meta-analysis of alpha", "authorString": "A",
                    "pubYear": "2024", "journalInfo": {"journal": {"title": "Journal B"}},
                    "pubTypeList": {"pubType": ["Systematic Review"]}, "isOpenAccess": "Y",
                }]},
            },
        ]

        def requester(_: str) -> dict:
            return responses.pop(0)

        corpus = harvest(
            2020, 2026, requester=requester,
            journal_strata={"top_general": ["Journal A", "Journal B"]},
        )
        self.assertEqual(corpus["summary"]["reported_hits"], 3)
        self.assertEqual(corpus["summary"]["unique_records"], 2)
        self.assertEqual(corpus["summary"]["development_candidates"], 1)
        self.assertEqual(corpus["summary"]["excluded_retracted"], 1)
        self.assertEqual(corpus["summary"]["excluded_non_reference"], 0)
        self.assertTrue(corpus["reference_policy"]["no_de_novo_human_adjudication"])
        self.assertTrue(all("abstract" not in record for record in corpus["records"]))

    def test_committed_corpus_is_large_and_summary_is_consistent(self) -> None:
        import json

        corpus = json.loads(
            (ROOT / "research/top-journal-training-corpus.json").read_text(encoding="utf-8")
        )
        records = corpus["records"]
        self.assertGreaterEqual(len(records), 1000)
        self.assertEqual(corpus["summary"]["unique_records"], len(records))
        self.assertEqual(
            corpus["summary"]["development_candidates"],
            sum(record["admission_status"] == "development_candidate" for record in records),
        )
        self.assertEqual(
            corpus["summary"]["held_for_integrity"],
            sum(record["admission_status"] == "hold_integrity_review" for record in records),
        )
        self.assertEqual(
            corpus["summary"]["excluded_non_reference"],
            sum(record["admission_status"] == "exclude_non_reference" for record in records),
        )
        self.assertFalse(any("abstract" in record for record in records))


if __name__ == "__main__":
    unittest.main()
