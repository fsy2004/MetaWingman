from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.metawingman_core.schema_guard import validate_document
from metawingman.scripts.metawingman_core.topic_construct_annotation import (
    TopicConstructAnnotationError,
    annotate_topic_construct_records,
)


ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TopicConstructAnnotationTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {
            "schema_version": "1.0", "manifest_id": "fixture-mesh-map-v1",
            "vocabulary": "NLM Medical Subject Headings", "vocabulary_version": "2026",
            "source_url": "https://www.nlm.nih.gov/mesh/meshhome.html",
            "target_reference_derived": False, "case_specific_target_terms_prohibited": True,
            "domains": [
                {"domain_id": "mental-health", "mesh_descriptor_terms": ["Depression", "Suicide"]},
                {"domain_id": "public-health", "mesh_descriptor_terms": ["Public Health"]},
            ],
        }

    def test_exact_mesh_assignments_and_registry_families_are_preserved(self) -> None:
        rows = [
            {"id": "pmid:1", "mesh_terms": ["Depression", "Humans"], "registry_ids": ["NCT01234567"], "study_family_ids": ["NCT01234567"], "construct_annotation_basis": "explicit_pubmed_xml_v1"},
            {"id": "pmid:2", "mesh_terms": ["Public Health"], "registry_ids": [], "study_family_ids": [], "decision_anchor_type": "guideline", "construct_annotation_basis": "explicit_pubmed_xml_v1"},
            {"id": "pmid:3", "mesh_terms": [], "registry_ids": [], "study_family_ids": [], "construct_annotation_basis": "explicit_pubmed_xml_v1"},
        ]
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            source = root / "records.jsonl"
            source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            output = root / "annotated.jsonl"
            receipt = root / "receipt.json"
            result = annotate_topic_construct_records(source, self.manifest(), output_path=output, receipt_path=receipt)
            actual = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(actual[0]["domain_ids"], ["mental-health"])
            self.assertEqual(actual[0]["study_family_ids"], ["NCT01234567"])
            self.assertEqual(actual[1]["domain_ids"], ["public-health"])
            self.assertEqual(actual[2]["domain_ids"], [])
            self.assertEqual(result["records_with_explicit_domains"], 2)
            self.assertEqual(result["records_with_explicit_study_families"], 1)
            self.assertEqual(result["decision_anchor_records"], 1)
            self.assertEqual(result["output_sha256"], _sha(output))

    def test_target_derived_mapping_fails_closed(self) -> None:
        manifest = self.manifest()
        manifest["target_reference_derived"] = True
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            source = Path(tmp) / "records.jsonl"
            source.write_text('{"id":"pmid:1","mesh_terms":[]}\n', encoding="utf-8")
            with self.assertRaisesRegex(TopicConstructAnnotationError, "target-reference-derived"):
                annotate_topic_construct_records(source, manifest, output_path=Path(tmp) / "out.jsonl", receipt_path=Path(tmp) / "receipt.json")

    def test_manifest_schema_rejects_duplicate_domain_terms(self) -> None:
        manifest = self.manifest()
        manifest["domains"][0]["mesh_descriptor_terms"] = ["Depression", "Depression"]
        with self.assertRaises(Exception):
            validate_document(manifest, "topic_construct_annotation_manifest")


if __name__ == "__main__":
    unittest.main()
