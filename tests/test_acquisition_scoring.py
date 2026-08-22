import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from metawingman.scripts.metawingman_core.acquisition_scoring import (
    ScoringError,
    match_reference_rows,
    score_rankings,
    validate_scoring_gate,
    extract_reference_rows,
    build_axis_reference_ids,
    score_axis_coverage,
)


class AcquisitionScoringTests(unittest.TestCase):
    def test_gate_requires_locked_twelve_slots_before_reference_access(self):
        plan = {"plan_id": "p", "case": {"case_id": "c", "operational_corpus_sha256": "a" * 64}}
        lock = {"status": "locked", "plan_id": "p", "case_id": "c", "corpus_sha256": "a" * 64, "locked_slots": 12}
        validate_scoring_gate(plan, lock, expected_slots=12)
        for key, value in (("status", "draft"), ("locked_slots", 11), ("corpus_sha256", "b" * 64)):
            broken = dict(lock); broken[key] = value
            with self.subTest(key=key), self.assertRaises(ScoringError):
                validate_scoring_gate(plan, broken, expected_slots=12)

    def test_reference_rows_match_by_doi_pmid_or_exact_normalized_title(self):
        corpus = [
            {"id": "a", "pmid": "12345678", "doi": "10.1234/abc", "title": "First diagnostic study."},
            {"id": "b", "pmid": "87654321", "doi": "", "title": "Second Study"},
            {"id": "c", "pmid": "", "doi": "10.5678/xyz", "title": "Third study"},
        ]
        rows = [
            {"doi": "https://doi.org/10.1234/ABC"},
            {"pmid": "87654321"},
            {"title": "Third study"},
            {"title": "unmapped report"},
        ]
        matched, audit = match_reference_rows(rows, corpus)
        self.assertEqual(matched, {"a", "b", "c"})
        self.assertEqual(audit["reference_rows"], 4)
        self.assertEqual(audit["mapped_rows"], 3)

    def test_scores_preregistered_rank_cutoffs_and_invalid_selection_rate(self):
        output = {
            "retrieval_candidate_ids": ["x", "a", "b", "c"],
            "selected_candidate_ids": ["a", "invented"],
        }
        scored = score_rankings(output, {"a", "c"}, valid_corpus_ids={"x", "a", "b", "c"}, cutoffs=(1, 2, 4))
        self.assertEqual(scored["recall_at_1"], 0.0)
        self.assertEqual(scored["recall_at_2"], 0.5)
        self.assertEqual(scored["recall_at_4"], 1.0)
        self.assertEqual(scored["selected_recall"], 0.5)
        self.assertEqual(scored["invalid_selected_rate"], 0.5)

    def test_standard_library_xlsx_extraction_uses_identity_headers(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "reference.xlsx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("xl/workbook.xml", '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Included" sheetId="1" r:id="rId1"/></sheets></workbook>')
                archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>')
                archive.writestr("xl/sharedStrings.xml", '<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>DOI</t></si><si><t>Title</t></si><si><t>10.1234/abc</t></si><si><t>First diagnostic study</t></si></sst>')
                archive.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row><row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c></row></sheetData></worksheet>')
            rows, audit = extract_reference_rows(path)
            self.assertEqual(rows[0]["doi"], "10.1234/abc")
            self.assertEqual(rows[0]["title"], "first diagnostic study")
            self.assertEqual(audit["reference_rows"], 1)

    def test_conclusion_axis_scoring_uses_reference_study_id_links(self):
        sheets = [
            ("References", [["Study ID", "Title"], ["S1", "First study"], ["S2", "Second study"]]),
            ("Ct Value", [["Study ID", "Ct value"], ["S1", 20]]),
            ("Age", [["Study ID", "Age"], ["S2", 40]]),
        ]
        corpus = [{"id": "a", "title": "First study"}, {"id": "b", "title": "Second study"}]
        axes, audit = build_axis_reference_ids(sheets, corpus, {"viral_burden": ("Ct Value",), "age": ("Age",)})
        self.assertEqual(axes, {"viral_burden": {"a"}, "age": {"b"}})
        self.assertEqual(audit["mapped_reference_studies"], 2)
        scored = score_axis_coverage({"retrieval_candidate_ids": ["a", "x", "b"]}, axes, cutoffs=(1, 3))
        self.assertEqual(scored["axis_macro_recall_at_1"], 0.5)
        self.assertEqual(scored["axis_macro_recall_at_3"], 1.0)
        self.assertEqual(scored["axes_with_any_at_1"], 0.5)


if __name__ == "__main__":
    unittest.main()
