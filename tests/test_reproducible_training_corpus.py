from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

from metawingman_core.schema_guard import validate_document  # noqa: E402
from metawingman_core.training_corpus import (  # noqa: E402
    TrainingCorpusError,
    audit_training_dataset,
    build_training_examples,
    build_training_plan,
    build_training_run_plan,
    classify_biomedical_stratum,
    fetch_training_plan,
)


TIMESTAMP = "2026-08-15T00:00:00Z"
ZERO_METRICS = {
    "pdf_pages": 0, "native_text_characters": 0, "pages_without_native_text": 0,
    "image_blocks": 0, "rotated_pages": 0, "jats_characters": 0,
    "jats_sections": 0, "jats_tables": 0, "jats_figures": 0, "jats_references": 0,
}
SPECIALTY_REGISTRY_PATH = ROOT / "metawingman/references/domain-packs/specialty-registry.json"


def specialty_registry_fixture() -> dict[str, object]:
    return json.loads(SPECIALTY_REGISTRY_PATH.read_text(encoding="utf-8"))


def corpus_record(index: int, journal: str = "Journal A") -> dict[str, object]:
    return {
        "record_id": f"epmc:MED:{index}", "source_id": f"MED:{index}",
        "title": f"Systematic review {index}", "authors": "Example A", "year": 2024,
        "journal": journal, "journal_stratum": "field", "doi": f"10.1/{index}",
        "pmid": str(index), "pmcid": f"PMC{1000 + index}",
        "publication_types": ["Systematic Review"], "is_open_access": True,
        "license": "cc by", "cited_by_count": 0, "source_url": f"https://example.org/{index}",
        "reference_status": "published_expert_reference",
        "integrity_status": "no_status_update_in_epmc_record", "status_update_types": [],
        "admission_status": "development_candidate",
        "family_assignment_status": "pending_review_family_clustering",
        "split_status": "unassigned_pending_family_audit",
    }


def fixture_plan(count: int = 3) -> dict[str, object]:
    records = [corpus_record(index, f"Journal {index % 2}") for index in range(1, count + 1)]
    corpus = {"records": records}
    families = {"families": [
        {
            "family_id": f"family:{index:016x}", "record_ids": [record["record_id"]],
            "status": "provisional_singleton", "suggested_split": "train",
            "split_status": "blocked_pending_family_audit",
        }
        for index, record in enumerate(records, start=1)
    ]}
    return build_training_plan(
        corpus, families, plan_id="fixture-plan", source_corpus_path="corpus.json",
        source_corpus_sha256="1" * 64, family_registry_path="families.json",
        family_registry_sha256="2" * 64, maximum_records=count, seed=9,
        train_fraction=0.6, created_at_utc=TIMESTAMP,
    )


def fixture_medical_plan(maximum_records: int = 12) -> dict[str, object]:
    titles = (
        "Cancer immunotherapy adverse events: systematic review",
        "Cardiovascular treatment outcomes: systematic review",
        "Diagnostic imaging for stroke: meta-analysis",
        "Depression prognosis: systematic review",
        "Infectious disease prevalence: systematic review",
        "Maternal prevention interventions: systematic review",
    )
    records = []
    for index in range(1, 25):
        record = corpus_record(index, f"Journal {index % 3}")
        record["title"] = titles[(index - 1) % len(titles)]
        records.append(record)
    families = {"families": [
        {
            "family_id": f"family:{index:016x}",
            "record_ids": [record["record_id"]],
            "status": "provisional_singleton",
            "suggested_split": "train",
            "split_status": "blocked_pending_family_audit",
        }
        for index, record in enumerate(records, start=1)
    ]}
    return build_training_plan(
        {"records": records},
        families,
        plan_id="fixture-biomedical-plan",
        source_corpus_path="corpus.json",
        source_corpus_sha256="1" * 64,
        family_registry_path="families.json",
        family_registry_sha256="2" * 64,
        maximum_records=maximum_records,
        seed=9,
        train_fraction=0.6,
        created_at_utc=TIMESTAMP,
        specialty_registry=specialty_registry_fixture(),
        specialty_registry_path="specialty-registry.json",
        specialty_registry_sha256="3" * 64,
    )


class ReproducibleTrainingCorpusTests(unittest.TestCase):
    def test_medical_strata_are_source_anchored_and_ignore_journal(self) -> None:
        left = corpus_record(1)
        left["title"] = "Cancer immunotherapy adverse events: systematic review"
        right = dict(left, journal="Unrelated Journal")
        self.assertEqual(
            classify_biomedical_stratum(left, specialty_registry_fixture()),
            classify_biomedical_stratum(right, specialty_registry_fixture()),
        )
        result = classify_biomedical_stratum(left, specialty_registry_fixture())
        self.assertEqual(result["primary_specialty"], "oncology")
        self.assertEqual(result["question_type"], "harms")
        self.assertEqual(result["label_status"], "deterministic_weak_candidate")
        self.assertTrue(result["evidence"])

    def test_plan_balances_composite_strata_before_repeating_them(self) -> None:
        plan = fixture_medical_plan(maximum_records=12)
        keys = [item["biomedical_stratum"]["sampling_key"] for item in plan["records"]]
        self.assertEqual(plan["schema_version"], "1.1")
        self.assertGreaterEqual(len(set(keys)), 4)
        validate_document(plan, "training_corpus_plan")

    def test_legacy_plan_remains_schema_version_one(self) -> None:
        plan = fixture_plan(3)
        self.assertEqual(plan["schema_version"], "1.0")
        self.assertNotIn("domain_policy", plan)

    def test_plan_is_deterministic_and_never_creates_held_out_records(self) -> None:
        first = fixture_plan(8)
        second = fixture_plan(8)
        self.assertEqual(first, second)
        validate_document(first, "training_corpus_plan")
        self.assertEqual({item["split"] for item in first["records"]}, {"train", "development"})
        family_splits: dict[str, set[str]] = {}
        for item in first["records"]:
            family_splits.setdefault(item["family_id"], set()).add(item["split"])
        self.assertTrue(all(len(value) == 1 for value in family_splits.values()))

    def test_integrity_and_license_fail_closed_during_planning(self) -> None:
        record = corpus_record(1)
        record["license"] = "all rights reserved"
        plan = build_training_plan(
            {"records": [record]}, {"families": [{
                "family_id": "family:0000000000000001", "record_ids": [record["record_id"]],
                "status": "provisional_singleton", "suggested_split": "train",
                "split_status": "blocked_pending_family_audit",
            }]}, plan_id="blocked-plan", source_corpus_path="corpus.json",
            source_corpus_sha256="1" * 64, family_registry_path="families.json",
            family_registry_sha256="2" * 64, created_at_utc=TIMESTAMP,
        )
        self.assertEqual(plan["records"], [])

    def test_pdf_failure_does_not_prevent_xml_retrieval(self) -> None:
        plan = fixture_plan(1)
        xml = b"<article><body><sec><title>Search methods</title><p>" + b"x" * 300 + b"</p></sec></body></article>"

        def request(url: str, **_: object) -> tuple[bytes, str]:
            if url.endswith("paper.pdf"):
                raise TrainingCorpusError("HTTP 403")
            return xml, url

        with tempfile.TemporaryDirectory() as directory, \
            patch("metawingman_core.training_corpus._oa_license", return_value=("CC BY", "verified_not_retracted")), \
            patch("metawingman_core.training_corpus._full_text_urls", return_value=("https://example.org/paper.pdf", "https://example.org/full.xml")), \
            patch("metawingman_core.training_corpus._request_bytes", side_effect=request), \
            patch("metawingman_core.training_corpus._parser_metrics", return_value=dict(ZERO_METRICS)):
            manifest = fetch_training_plan(
                plan, Path(directory), manifest_id="fixture-manifest", delay_seconds=0,
                created_at_utc=TIMESTAMP,
            )
            self.assertEqual(manifest["summary"]["partial"], 1)
            self.assertEqual(manifest["summary"]["xml_files"], 1)
            self.assertEqual(manifest["summary"]["pdf_files"], 0)
            self.assertIn("pdf_retrieval_failed", manifest["documents"][0]["failure_reasons"][0])
            with patch("metawingman_core.training_corpus._oa_license", side_effect=AssertionError("cache miss")):
                replay = fetch_training_plan(
                    plan, Path(directory), manifest_id="fixture-manifest", delay_seconds=0,
                    created_at_utc=TIMESTAMP,
                )
            self.assertEqual(replay, manifest)

    def test_examples_and_run_plan_remain_weak_supervision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            xml_path = root / "train/family-1/PMC1.xml"
            xml_path.parent.mkdir(parents=True)
            xml_path.write_text(
                "<article><body>"
                "<sec><title>Search strategy</title><p>We searched MEDLINE and Embase from inception using a prespecified strategy with independent verification and documented dates.</p></sec>"
                "<sec><title>Risk of bias assessment</title><p>Two reviewers assessed risk of bias at the result level and recorded supporting judgments for every domain.</p></sec>"
                "</body></article>", encoding="utf-8",
            )
            xml_sha = hashlib.sha256(xml_path.read_bytes()).hexdigest()
            manifest = {
                "schema_version": "1.0", "manifest_id": "fixture-manifest",
                "created_at_utc": TIMESTAMP, "plan_id": "fixture-plan", "plan_sha256": "3" * 64,
                "source_policy": {
                    "metadata_api": "Europe PMC REST", "full_text_api": "Europe PMC OA",
                    "license_api": "PMC OA Web Service", "public_https_only": True,
                    "article_level_license_required": True, "retractions_rejected": True,
                },
                "summary": {"planned": 1, "complete": 0, "partial": 1, "failed": 0, "pdf_files": 0, "xml_files": 1, "total_bytes": xml_path.stat().st_size},
                "documents": [{
                    "document_id": "training-document:PMC1", "record_id": "epmc:MED:1",
                    "family_id": "family:0000000000000001", "split": "train", "pmcid": "PMC1",
                    "title": "Fixture review", "license": "cc by",
                    "integrity_status": "verified_not_retracted", "retrieval_status": "partial",
                    "failure_reasons": ["no_open_access_pdf_url"],
                    "artifacts": [{"kind": "jats_xml", "source_url": "https://example.org/full.xml", "relative_path": xml_path.relative_to(root).as_posix(), "media_type": "application/xml", "bytes": xml_path.stat().st_size, "sha256": xml_sha}],
                    "parser_metrics": dict(ZERO_METRICS), "label_status": "source_document_only_not_gold",
                }],
            }
            validate_document(manifest, "training_document_manifest")
            examples = build_training_examples(manifest, root, minimum_characters=20)
            self.assertEqual(len(examples), 4)
            self.assertTrue(all(not item["gold_label"] for item in examples))
            examples_path = root / "examples.jsonl"
            examples_path.write_text("\n".join(json.dumps(item) for item in examples) + "\n", encoding="utf-8")
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            run_plan = build_training_run_plan(
                manifest, manifest_path, examples_path, examples,
                run_plan_id="fixture-run", created_at_utc=TIMESTAMP,
            )
            run_plan_path = root / "run-plan.json"
            run_plan_path.write_text(json.dumps(run_plan), encoding="utf-8")
            validate_document(run_plan, "training_run_plan")
            self.assertEqual(run_plan["dataset"]["held_out_examples"], 0)
            self.assertEqual(run_plan["execution_state"], "planned_not_trained")

    def test_artifact_drift_is_detected_before_training(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "train/family-1/PMC1.xml"
            path.parent.mkdir(parents=True)
            path.write_text("<article/>", encoding="utf-8")
            artifact_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            plan = fixture_plan(1)
            planned = plan["records"][0]
            manifest = {
                "schema_version": "1.0", "manifest_id": "fixture-manifest", "created_at_utc": TIMESTAMP,
                "plan_id": plan["plan_id"], "plan_sha256": "3" * 64,
                "source_policy": {"metadata_api": "Europe PMC REST", "full_text_api": "Europe PMC OA", "license_api": "PMC OA Web Service", "public_https_only": True, "article_level_license_required": True, "retractions_rejected": True},
                "summary": {"planned": 1, "complete": 0, "partial": 1, "failed": 0, "pdf_files": 0, "xml_files": 1, "total_bytes": path.stat().st_size},
                "documents": [{
                    "document_id": "training-document:" + planned["pmcid"], "record_id": planned["record_id"],
                    "family_id": planned["family_id"], "split": planned["split"], "pmcid": planned["pmcid"],
                    "title": planned["title"], "license": "cc by", "integrity_status": "verified_not_retracted",
                    "retrieval_status": "partial", "failure_reasons": ["no_open_access_pdf_url"],
                    "artifacts": [{"kind": "jats_xml", "source_url": "https://example.org/full.xml", "relative_path": path.relative_to(root).as_posix(), "media_type": "application/xml", "bytes": path.stat().st_size, "sha256": artifact_hash}],
                    "parser_metrics": dict(ZERO_METRICS), "label_status": "source_document_only_not_gold",
                }],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            examples_path = root / "examples.jsonl"
            examples_path.write_text("", encoding="utf-8")
            run_plan = {
                "schema_version": "1.0", "run_plan_id": "fixture-run", "created_at_utc": TIMESTAMP,
                "dataset": {"manifest_path": manifest_path.as_posix(), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "examples_path": examples_path.as_posix(), "examples_sha256": hashlib.sha256(examples_path.read_bytes()).hexdigest(), "train_examples": 0, "development_examples": 0, "held_out_examples": 0},
                "model_contract": {"provider_neutral": True, "base_model": None, "revision": None, "tokenizer_revision": None, "license_review_required_before_training": True},
                "objectives": ["section_role_classification"],
                "evaluation": {"unit": "review_family", "metrics": ["macro_f1"], "selection_uses_development_only": True, "scientific_claims_disabled": True},
                "contamination_controls": {"family_isolation": True, "journal_feature_forbidden": True, "published_answer_is_not_oracle": True, "model_memory_risk_recorded": True},
                "execution_state": "planned_not_trained",
            }
            path.write_text("<article>tampered</article>", encoding="utf-8")
            audit = audit_training_dataset(plan, manifest, [], run_plan, root, manifest_path, examples_path)
            self.assertFalse(audit["valid"])
            self.assertTrue(any("artifact hash or size drift" in issue for issue in audit["issues"]))


if __name__ == "__main__":
    unittest.main()
