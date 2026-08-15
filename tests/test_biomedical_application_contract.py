from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "metawingman"
SCRIPTS = SKILL_ROOT / "scripts"
PACK_DIR = SKILL_ROOT / "references" / "domain-packs"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.schema_guard import SchemaValidationError, load_schema, validate_document  # noqa: E402


TIMESTAMP = "2026-08-15T00:00:00Z"
APPLICATION_DOMAIN = "human_health_clinical_translational_biomedicine"


def biomedical_context_fixture(review_family: str = "intervention") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "context_id": "ctx-1",
        "application_domain": APPLICATION_DOMAIN,
        "status": "draft",
        "review_family": review_family,
        "primary_specialty": "general-medicine",
        "secondary_specialties": [],
        "question_framework": {
            "framework": "PICO",
            "source_text": "Adults receiving an intervention",
            "normalized_concepts": [],
            "unresolved_terms": ["intervention"],
        },
        "terminology_releases": [],
        "source_classes": ["bibliographic_database"],
        "languages": ["en"],
        "geographies": [],
        "ood_assessment": {"status": "in_scope", "reason_codes": []},
        "created_at_utc": TIMESTAMP,
        "updated_at_utc": TIMESTAMP,
    }


def domain_pack_fixture() -> dict[str, object]:
    return json.loads((PACK_DIR / "biomedical-foundation.json").read_text(encoding="utf-8"))


class BiomedicalApplicationContractTests(unittest.TestCase):
    def test_new_schemas_are_valid_draft_2020_12(self) -> None:
        for name in (
            "biomedical_context",
            "domain_pack_manifest",
            "domain_routing_decision",
            "biomedical_training_stratum",
            "domain_coverage_report",
        ):
            Draft202012Validator.check_schema(load_schema(name))

    def test_biomedical_context_requires_human_health_domain(self) -> None:
        context = biomedical_context_fixture()
        validate_document(context, "biomedical_context")
        context["application_domain"] = "veterinary"
        with self.assertRaises(SchemaValidationError):
            validate_document(context, "biomedical_context")

    def test_context_is_closed_and_preserves_source_wording(self) -> None:
        context = biomedical_context_fixture()
        self.assertEqual(context["question_framework"]["source_text"], "Adults receiving an intervention")
        context["inferred_disease"] = "forbidden"
        with self.assertRaises(SchemaValidationError):
            validate_document(context, "biomedical_context")

    def test_domain_pack_cannot_claim_method_override(self) -> None:
        pack = domain_pack_fixture()
        validate_document(pack, "domain_pack_manifest")
        for key in (
            "may_override_protocol",
            "may_override_authority",
            "may_override_estimand",
            "may_grant_tool_permissions",
            "may_promote_model_output_to_gold",
        ):
            invalid = copy.deepcopy(pack)
            invalid["constraints"][key] = True
            with self.subTest(key=key), self.assertRaises(SchemaValidationError):
                validate_document(invalid, "domain_pack_manifest")

    def test_all_pack_manifests_validate(self) -> None:
        pack_ids: set[str] = set()
        for path in sorted(PACK_DIR.glob("*.json")):
            pack = json.loads(path.read_text(encoding="utf-8"))
            validate_document(pack, "domain_pack_manifest")
            self.assertNotIn(pack["pack_id"], pack_ids)
            pack_ids.add(pack["pack_id"])
        self.assertEqual(
            pack_ids,
            {
                "biomedical-foundation",
                "profile-diagnostic",
                "profile-harms",
                "profile-intervention",
                "profile-prognostic",
                "specialty-registry",
            },
        )

    def test_foundation_supports_the_existing_profile_catalog(self) -> None:
        profile_schema = load_schema("review_profile")
        expected = set(profile_schema["properties"]["review_family"]["enum"])
        pack = domain_pack_fixture()
        self.assertEqual(set(pack["supported_review_families"]), expected)
        self.assertEqual(
            set(pack["capabilities"]),
            {"terminology_normalization", "source_selection", "ood_detection", "domain_routing"},
        )

    def test_specialty_registry_has_required_medical_breadth(self) -> None:
        registry = json.loads((PACK_DIR / "specialty-registry.json").read_text(encoding="utf-8"))
        ids = {item["specialty_id"] for item in registry["specialties"]}
        self.assertTrue(
            {
                "general-medicine",
                "oncology",
                "cardiovascular-medicine",
                "neurology",
                "infectious-disease",
                "mental-health",
                "maternal-child-health",
                "public-health",
                "drug-safety",
                "diagnostics",
                "imaging",
                "clinical-omics",
            }.issubset(ids)
        )


if __name__ == "__main__":
    unittest.main()
