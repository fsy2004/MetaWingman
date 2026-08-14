from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from harvest_top_journal_corpus import harvest  # noqa: E402


class TopJournalCorpusTests(unittest.TestCase):
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
        self.assertFalse(any("abstract" in record for record in records))


if __name__ == "__main__":
    unittest.main()
