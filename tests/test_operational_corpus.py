import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.operational_corpus import load_jsonl_records, sanitize_records


class OperationalCorpusTests(unittest.TestCase):
    def test_jsonl_loader_preserves_unicode_line_separator_inside_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.jsonl"
            record = {"id": "x", "abstract": "before\u2028after"}
            path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
            self.assertEqual(load_jsonl_records(path), [record])

    def test_forbidden_family_identity_and_postcutoff_are_removed(self):
        records = [
            {"id": "pmid:1", "pmid": "1", "doi": "10.1371/journal.pmed.1003735", "title": "unrelated", "first_publication_date": "2021-08-01"},
            {"id": "pmid:2", "pmid": "2", "doi": "", "title": "Accuracy of novel antigen rapid diagnostics for SARS-CoV-2: A living systematic review and meta-analysis", "first_publication_date": "2021 Aug"},
            {"id": "pmid:3", "pmid": "3", "doi": "", "title": "eligible diagnostic study", "first_publication_date": "2021-09-01"},
            {"id": "pmid:4", "pmid": "4", "doi": "", "title": "date missing", "first_publication_date": ""},
            {"id": "pmid:5", "pmid": "5", "doi": "10.1000/source", "title": "eligible diagnostic study", "first_publication_date": "2021 Jul 15"},
        ]
        cleaned, audit = sanitize_records(
            records,
            cutoff="2021-08-31",
            forbidden_identity_patterns=[
                "10.1371/journal.pmed.1003735",
                "Accuracy of novel antigen rapid diagnostics for SARS-CoV-2: A living systematic review and meta-analysis",
            ],
        )
        self.assertEqual([record["id"] for record in cleaned], ["pmid:5"])
        self.assertEqual(audit["excluded_forbidden_identity"], 2)
        self.assertEqual(audit["excluded_post_cutoff"], 1)
        self.assertEqual(audit["excluded_unverifiable_date"], 1)

    def test_month_precision_before_or_at_cutoff_is_accepted(self):
        cleaned, audit = sanitize_records(
            [{"id": "x", "title": "source", "doi": "", "pmid": "", "first_publication_date": "2021 Aug"}],
            cutoff="2021-08-31",
            forbidden_identity_patterns=[],
        )
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(audit["included"], 1)


if __name__ == "__main__":
    unittest.main()
