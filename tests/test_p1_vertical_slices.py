from __future__ import annotations

import importlib.util
import math
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "metawingman" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.document_ingestor import DocumentIngestError, ingest_document  # noqa: E402
from metawingman_core.effect_recalculator import (  # noqa: E402
    EffectCalculationError,
    calculate_effect,
)
from metawingman_core.protocol_compiler import compile_full_protocol  # noqa: E402
from metawingman_core.schema_guard import validate_document  # noqa: E402
from metawingman_core.screening_engine import screen_record  # noqa: E402


TIMESTAMP = "2026-08-13T00:00:00Z"
ZERO_HASH = "0" * 64


def criteria() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "protocol_version": "1.0",
        "status": "frozen",
        "criteria": [
            {
                "criterion_id": "adult",
                "domain": "population",
                "label": "Adults",
                "predicate": {
                    "field": "minimum_age",
                    "operator": "gte",
                    "value": 18,
                    "unit": "years",
                    "normalization": "years",
                },
                "missing_policy": "unclear",
                "full_text_required": True,
                "status": "operational",
                "source_section": "Eligibility criteria",
            },
            {
                "criterion_id": "rct",
                "domain": "design",
                "label": "Randomized trial",
                "predicate": {
                    "field": "design",
                    "operator": "equals",
                    "value": "randomized trial",
                    "unit": None,
                    "normalization": "casefold",
                },
                "missing_policy": "unclear",
                "full_text_required": False,
                "status": "operational",
                "source_section": "Eligibility criteria",
            },
        ],
    }


def extraction_candidate(candidate_id: str, field: str, value: float, data_type: str = "number") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "candidate_id": candidate_id,
        "document_id": "document-1",
        "report_id": "report-1",
        "study_id": "study-1",
        "result_id": "result-1",
        "field": field,
        "value": {"raw": value, "normalized": value, "data_type": data_type},
        "unit": None,
        "anchor_ids": [f"anchor-{candidate_id}"],
        "channel": "table",
        "created_by": {"type": "tool", "id": "fixture", "version": "1.0"},
        "confidence": 1.0,
        "derivation": {
            "method": "direct", "formula_or_rule": "verbatim table cell",
            "input_candidate_ids": [], "tool": "fixture", "tool_version": "1.0",
        },
        "status": "accepted",
        "verification": {
            "method": "independent_extraction", "status": "passed",
            "verified_by": "fixture-reviewer", "independently_derived": True,
            "verified_at_utc": TIMESTAMP, "discrepancy": "",
        },
        "created_at_utc": TIMESTAMP,
    }


def full_protocol() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "protocol_id": "protocol-1",
        "protocol_version": "1.0",
        "status": "frozen",
        "profile_id": "profile-1",
        "decision_context": {
            "decision": "Estimate benefit for treatment selection.",
            "stakeholders": ["patients", "clinicians"],
            "setting": "Outpatient care",
            "intended_use": "Shared decision making",
        },
        "review_questions": [{
            "question_id": "question-1",
            "objective": "Estimate the intervention effect.",
            "framework": "PICO",
            "dimensions": [
                {"name": "population", "value": "Adults", "operational_definition": "Age at least 18 years."},
                {"name": "intervention", "value": "Treatment A", "operational_definition": "Any licensed dose."},
                {"name": "comparator", "value": "Placebo", "operational_definition": "Matched placebo."},
                {"name": "outcome", "value": "Clinical event", "operational_definition": "Prespecified event definition."},
            ],
        }],
        "synthesis_questions": [{
            "synthesis_id": "synthesis-1",
            "review_question_ids": ["question-1"],
            "population": "Eligible adults",
            "contrast": "Treatment A versus placebo",
            "outcome_id": "outcome-1",
            "time_window": "12 weeks",
            "effect_measure": "risk ratio",
            "estimand": {
                "estimand_id": "estimand-1",
                "target_population": "Eligible adults",
                "contrast": "Assignment to Treatment A versus placebo",
                "outcome": "Clinical event",
                "time_horizon": "12 weeks",
                "population_summary": "Average risk ratio",
                "analysis_unit": "randomized participant",
                "conditioning_set": [],
            },
            "decision_thresholds": [{
                "threshold_id": "threshold-1", "type": "minimal_importance",
                "value": 0.9, "unit": "risk ratio", "direction": "less",
                "rationale": "Prospective minimum important benefit.",
            }],
            "poolability_rule": "Pool only aligned estimands and time windows.",
        }],
        "outcome_hierarchy": [{
            "outcome_id": "outcome-1", "label": "Clinical event", "role": "primary",
            "construct": "Participants with a clinical event",
            "preferred_measures": ["risk ratio"], "time_windows": ["12 weeks"],
            "result_selection_rule": "Use the prespecified intention-to-treat result.",
        }],
        "criteria_artifact": {
            "path": "01_protocol/protocol_criteria.json", "schema": "protocol_criteria",
            "status": "frozen", "sha256": ZERO_HASH,
        },
        "source_plan": [{
            "source_id": "pubmed", "source_type": "bibliographic_database",
            "database": "MEDLINE", "platform": "PubMed", "access_route": "public_api",
            "required": True, "query_file": "02_search/queries/pubmed.txt",
            "coverage": "Inception to 2026-08-13",
        }],
        "amendment_policy": {
            "freeze_trigger": "Human lead approval",
            "prospective_change_rule": "Record before affected results are inspected.",
            "post_hoc_label_required": True, "rerun_impact_analysis": True,
        },
        "created_at_utc": TIMESTAMP,
        "frozen_at_utc": TIMESTAMP,
        "frozen_by": "human-lead",
    }


class ProtocolPlanTests(unittest.TestCase):
    def test_complete_protocol_is_operational(self) -> None:
        result = compile_full_protocol(full_protocol())
        self.assertTrue(result.ready_to_freeze)

    def test_outcome_timepoint_mismatch_downgrades_freeze(self) -> None:
        candidate = full_protocol()
        candidate["synthesis_questions"][0]["time_window"] = "52 weeks"
        result = compile_full_protocol(candidate)
        self.assertFalse(result.ready_to_freeze)
        self.assertEqual(result.document["status"], "draft")
        self.assertTrue(any(issue.code == "time_window_outside_outcome_plan" for issue in result.issues))


class ScreeningTests(unittest.TestCase):
    def test_missing_abstract_information_abstains_instead_of_excluding(self) -> None:
        assessment = screen_record(
            criteria(),
            {
                "record_id": "record-1",
                "fields": {"design": "Randomized Trial"},
                "anchors": {"design": ["anchor-design"]},
                "confidence": {"design": 0.99},
            },
            stage="title_abstract",
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(assessment["policy_decision"]["recommendation"], "abstain")
        self.assertIn("missing_information_not_equivalent_to_exclusion", assessment["policy_decision"]["reason_codes"])

    def test_anchored_hard_negative_can_be_excluded(self) -> None:
        assessment = screen_record(
            criteria(),
            {
                "record_id": "record-2",
                "fields": {"minimum_age": 21, "design": "observational cohort"},
                "anchors": {"minimum_age": ["anchor-age"], "design": ["anchor-design"]},
                "confidence": {"minimum_age": 0.99, "design": 0.99},
            },
            stage="full_text",
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(assessment["policy_decision"]["recommendation"], "exclude")
        self.assertEqual(assessment["policy_decision"]["primary_reason_code"], "rct")

    def test_counterevidence_challenges_exclusion(self) -> None:
        assessment = screen_record(
            criteria(),
            {
                "record_id": "record-3",
                "fields": {"minimum_age": 21, "design": "observational cohort"},
                "anchors": {"minimum_age": ["anchor-age"], "design": ["anchor-design"]},
                "confidence": {"minimum_age": 0.99, "design": 0.99},
                "counterevidence": {"rct": ["anchor-randomization-methods"]},
            },
            stage="full_text",
            created_at_utc=TIMESTAMP,
        )
        self.assertEqual(assessment["opposition"]["verdict"], "challenge")
        self.assertEqual(assessment["policy_decision"]["recommendation"], "abstain")


class DocumentIngestionTests(unittest.TestCase):
    def test_document_byte_budget_is_enforced_before_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "oversized.txt"
            source.parent.mkdir()
            source.write_bytes(b"x" * 32)
            with self.assertRaises(DocumentIngestError):
                ingest_document(
                    source, root, document_id="oversized", report_id="report-1",
                    source_type="supplement", access_route="user_provided",
                    license_name="User-provided", max_document_bytes=16,
                    retrieved_at_utc=TIMESTAMP,
                )
            self.assertFalse(
                (root / "02_search/retrieval/documents/oversized/original/oversized.txt").exists()
            )

    def test_utf8_document_creates_immutable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "supplement.txt"
            source.parent.mkdir()
            source.write_text("Table S1\nOutcome data\n", encoding="utf-8")
            state = ingest_document(
                source, root, document_id="document-1", report_id="report-1",
                source_type="supplement", access_route="user_provided",
                license_name="User-provided for this review", retrieved_at_utc=TIMESTAMP,
            )
            validate_document(state, "document_state")
            self.assertEqual(state["parse_status"], "ready")
            self.assertEqual(state["representations"][0]["type"], "native_text")
            self.assertTrue((root / state["source"]["artifact_path"]).is_file())

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is optional")
    def test_pdf_text_and_page_image_are_registered(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "article.pdf"
            source.parent.mkdir()
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((72, 72), "Randomized trial result")
            pdf.save(source)
            pdf.close()
            state = ingest_document(
                source, root, document_id="document-pdf", report_id="report-1",
                source_type="article", access_route="open_access",
                license_name="CC BY 4.0", render_pages=True, retrieved_at_utc=TIMESTAMP,
            )
            types = [item["type"] for item in state["representations"]]
            self.assertIn("native_text", types)
            self.assertIn("page_image", types)
            self.assertEqual(state["parse_status"], "ready")

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is optional")
    def test_pdf_page_and_render_budgets_are_enforced(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "budget.pdf"
            source.parent.mkdir()
            pdf = fitz.open()
            pdf.new_page(width=612, height=792)
            pdf.new_page(width=612, height=792)
            pdf.save(source)
            pdf.close()
            with self.assertRaises(DocumentIngestError):
                ingest_document(
                    source, root, document_id="page-budget", report_id="report-1",
                    source_type="article", access_route="user_provided",
                    license_name="User-provided", max_pages=1,
                )
            with self.assertRaises(DocumentIngestError):
                ingest_document(
                    source, root, document_id="pixel-budget", report_id="report-1",
                    source_type="article", access_route="user_provided",
                    license_name="User-provided", render_pages=True,
                    max_render_pixels=100,
                )

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is optional")
    def test_malformed_and_password_protected_pdfs_fail_closed(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "incoming"
            incoming.mkdir()
            malformed = incoming / "malformed.pdf"
            malformed.write_bytes(b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\n")
            with self.assertRaises(DocumentIngestError):
                ingest_document(
                    malformed, root, document_id="malformed", report_id="report-1",
                    source_type="article", access_route="user_provided",
                    license_name="User-provided",
                )

            protected = incoming / "protected.pdf"
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_text((72, 72), "Protected source")
            pdf.save(
                protected,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw="owner-password",
                user_pw="reader-password",
            )
            pdf.close()
            with self.assertRaisesRegex(DocumentIngestError, "user-authorized decryption"):
                ingest_document(
                    protected, root, document_id="protected", report_id="report-1",
                    source_type="article", access_route="user_provided",
                    license_name="User-provided",
                )

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF is optional")
    def test_complex_synthetic_pdf_preserves_page_geometry_and_text(self) -> None:
        import fitz

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "incoming" / "multimodal-layout.pdf"
            source.parent.mkdir()
            pdf = fitz.open()
            page = pdf.new_page(width=842, height=595)
            page.set_rotation(90)
            page.insert_textbox(fitz.Rect(40, 40, 380, 180), "Table 1\nArm A  20/100\nArm B  10/100")
            page.draw_rect(fitz.Rect(420, 60, 760, 300), color=(0, 0, 0), fill=(0.9, 0.9, 0.9))
            page.insert_text((450, 180), "Figure panel A")
            pdf.new_page(width=612, height=792).insert_text((72, 72), "Supplementary methods")
            pdf.save(source, garbage=4, deflate=True)
            pdf.close()
            state = ingest_document(
                source, root, document_id="complex-layout", report_id="report-1",
                source_type="supplement", access_route="user_provided",
                license_name="Synthetic test fixture", render_pages=True,
                max_pages=2, max_render_pixels=20_000_000,
                retrieved_at_utc=TIMESTAMP,
            )
            self.assertEqual(len([x for x in state["representations"] if x["type"] == "page_image"]), 2)
            text = (root / "02_search/retrieval/documents/complex-layout/representations/native_text.txt").read_text(encoding="utf-8")
            self.assertIn("Arm A", text)
            self.assertIn("Supplementary methods", text)


class EffectRecalculationTests(unittest.TestCase):
    def _calculate(self, measure: str, values: dict[str, float], correction: float | None = None) -> dict[str, object]:
        candidates = [
            extraction_candidate(f"candidate-{index}", field, value, "integer" if float(value).is_integer() else "number")
            for index, (field, value) in enumerate(values.items(), start=1)
        ]
        return calculate_effect(
            candidates, effect_id=f"effect-{measure}", result_id="result-1",
            measure=measure, direction="descriptive",
            continuity_correction=correction, created_at_utc=TIMESTAMP,
        )

    def test_binary_and_continuous_formulas(self) -> None:
        binary = {
            "events_intervention": 20, "total_intervention": 100,
            "events_control": 10, "total_control": 100,
        }
        rr = self._calculate("log_risk_ratio", binary)
        self.assertAlmostEqual(rr["estimate"], math.log(2.0), places=12)
        self.assertAlmostEqual(rr["variance"], 0.13, places=12)
        self.assertAlmostEqual(rr["back_transformed"]["estimate"], 2.0, places=12)
        odds = self._calculate("log_odds_ratio", binary)
        self.assertAlmostEqual(odds["back_transformed"]["estimate"], 2.25, places=12)
        difference = self._calculate("risk_difference", binary)
        self.assertAlmostEqual(difference["estimate"], 0.1, places=12)

        continuous = {
            "mean_intervention": 10, "sd_intervention": 2, "total_intervention": 50,
            "mean_control": 8, "sd_control": 3, "total_control": 50,
        }
        md = self._calculate("mean_difference", continuous)
        self.assertAlmostEqual(md["estimate"], 2.0, places=12)
        self.assertAlmostEqual(md["variance"], 0.26, places=12)
        smd = self._calculate("standardized_mean_difference", continuous)
        self.assertGreater(smd["estimate"], 0)
        self.assertGreater(smd["variance"], 0)

    def test_correlation_proportion_and_zero_cell_policy(self) -> None:
        fisher = self._calculate("fisher_z", {"correlation": 0.5, "total": 30})
        self.assertAlmostEqual(fisher["estimate"], math.atanh(0.5), places=12)
        self.assertAlmostEqual(fisher["back_transformed"]["estimate"], 0.5, places=12)
        proportion = self._calculate("logit_proportion", {"events": 25, "total": 100})
        self.assertAlmostEqual(proportion["back_transformed"]["estimate"], 0.25, places=12)
        binary_zero = {
            "events_intervention": 0, "total_intervention": 20,
            "events_control": 2, "total_control": 20,
        }
        with self.assertRaises(EffectCalculationError):
            self._calculate("log_odds_ratio", binary_zero)
        corrected = self._calculate("log_odds_ratio", binary_zero, correction=0.5)
        self.assertTrue(math.isfinite(corrected["estimate"]))


if __name__ == "__main__":
    unittest.main()
