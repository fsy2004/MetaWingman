import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

import harvest_top_journal_corpus  # noqa: E402
from metawingman_core.schema_guard import validate_document  # noqa: E402


def _item(identifier: str, title: str, journal: str = "Example Journal") -> dict:
    return {
        "id": identifier,
        "source": "MED",
        "title": title,
        "pubYear": "2023",
        "journalInfo": {"journal": {"title": journal}},
        "authorString": "Doe J",
        "doi": f"10.1000/{identifier}",
        "pmid": str(100000 + int(identifier)),
        "pmcid": f"PMC{identifier}",
        "pubTypeList": {"pubType": ["Systematic Review"]},
        "isOpenAccess": "Y",
        "license": "cc by",
        "citedByCount": 3,
    }


class BroadQueryHarvestTests(unittest.TestCase):
    def test_broad_query_records_carry_stratum_and_policy(self) -> None:
        def fake_requester(url: str) -> dict:
            if "JOURNAL" in url:
                return {"version": "9.0", "hitCount": 0, "resultList": {"result": []}, "nextCursorMark": "*"}
            return {
                "version": "9.0",
                "hitCount": 2,
                "resultList": {"result": [
                    _item("1", "Physical exercise for fibromyalgia: a systematic review"),
                    _item("2", "Diet and rheumatoid arthritis: meta-analysis"),
                ]},
                "nextCursorMark": "*",
            }

        with patch.object(harvest_top_journal_corpus, "_request_json", side_effect=fake_requester):
            corpus = harvest_top_journal_corpus.harvest(
                2018, 2026,
                requester=fake_requester,
                journal_strata={"top_general_medical": ["BMJ"]},
                broad_queries=[("broad_open_access", "review query")],
                broad_query_limit=500,
            )
        validate_document(corpus, "top_journal_training_corpus")
        self.assertEqual(corpus["summary"]["unique_records"], 2)
        self.assertTrue(all(r["journal_stratum"] == "broad_open_access" for r in corpus["records"]))
        self.assertEqual(corpus["sampling_policy"]["broad_queries"][0]["stratum"], "broad_open_access")

    def test_broad_query_limit_stops_pagination(self) -> None:
        calls = {"count": 0}

        def fake_requester(url: str) -> dict:
            if "JOURNAL" in url:
                return {"version": "9.0", "hitCount": 0, "resultList": {"result": []}, "nextCursorMark": "*"}
            calls["count"] += 1
            return {
                "version": "9.0",
                "hitCount": 2000,
                "resultList": {"result": [_item(str(i), f"Review of topic {i}") for i in range(1000)]},
                "nextCursorMark": "cursor-next" if calls["count"] == 1 else "*",
            }

        with patch.object(harvest_top_journal_corpus, "_request_json", side_effect=fake_requester):
            corpus = harvest_top_journal_corpus.harvest(
                2018, 2026,
                requester=fake_requester,
                journal_strata={"top_general_medical": ["BMJ"]},
                broad_queries=[("broad_open_access", "review query")],
                broad_query_limit=500,
            )
        self.assertEqual(corpus["summary"]["unique_records"], 500)
        self.assertEqual(calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
