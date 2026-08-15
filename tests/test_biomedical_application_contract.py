from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "metawingman"
SCRIPTS = SKILL_ROOT / "scripts"
PACK_DIR = SKILL_ROOT / "references" / "domain-packs"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.schema_guard import SchemaValidationError, load_schema, validate_document  # noqa: E402
from metawingman_core.biomedical_domain import (  # noqa: E402
    BiomedicalDomainError,
    load_domain_packs,
    resolve_context,
    route_domain_packs,
)


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

    def test_resolver_preserves_source_text_and_unresolved_terms(self) -> None:
        result = resolve_context(
            {
                "context_id": "ctx-resolve",
                "review_family": "intervention",
                "source_text": "Adults with an unmapped syndrome receiving aspirin",
                "declared_specialties": ["cardiovascular-medicine"],
            },
            load_domain_packs(PACK_DIR),
            TIMESTAMP,
        )
        self.assertEqual(
            result["question_framework"]["source_text"],
            "Adults with an unmapped syndrome receiving aspirin",
        )
        self.assertIn("unmapped syndrome", result["question_framework"]["unresolved_terms"])
        self.assertEqual(result["primary_specialty"], "cardiovascular-medicine")

    def test_resolver_only_normalizes_a_pack_matched_source_span(self) -> None:
        result = resolve_context(
            {
                "context_id": "ctx-match",
                "review_family": "diagnostic",
                "source_text": "Diagnostic imaging for stroke",
                "declared_specialties": ["diagnostics", "imaging"],
            },
            load_domain_packs(PACK_DIR),
            TIMESTAMP,
        )
        phrases = {item["source_phrase"].casefold() for item in result["question_framework"]["normalized_concepts"]}
        self.assertIn("diagnostic", phrases)
        self.assertIn("imaging", phrases)
        self.assertIn("stroke", phrases)

    def test_high_risk_route_abstains_without_validated_profile_pack(self) -> None:
        packs = [domain_pack_fixture()]
        result = route_domain_packs(
            biomedical_context_fixture("diagnostic"), packs, "appraisal", "high", TIMESTAMP
        )
        self.assertEqual(result["status"], "abstained")
        self.assertIn("missing_profile_pack", result["reason_codes"])
        validate_document(result, "domain_routing_decision")

    def test_high_risk_route_selects_foundation_then_profile(self) -> None:
        result = route_domain_packs(
            biomedical_context_fixture("diagnostic"),
            load_domain_packs(PACK_DIR),
            "appraisal",
            "high",
            TIMESTAMP,
        )
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["selected_pack_ids"][:2], ["biomedical-foundation", "profile-diagnostic"])

    def test_hash_tampering_is_fail_closed(self) -> None:
        packs = load_domain_packs(PACK_DIR)
        tampered = copy.deepcopy(packs)
        tampered[0]["capabilities"].append("unhashed_capability")
        with self.assertRaises(BiomedicalDomainError):
            route_domain_packs(
                biomedical_context_fixture("intervention"), tampered, "screening", "moderate", TIMESTAMP
            )

    def test_route_cli_writes_valid_abstention_and_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            context_path = root / "context.json"
            out_path = root / "route.json"
            packs = root / "packs"
            packs.mkdir()
            context_path.write_text(json.dumps(biomedical_context_fixture("diagnostic")), encoding="utf-8")
            (packs / "biomedical-foundation.json").write_text(
                (PACK_DIR / "biomedical-foundation.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "route_domain_packs.py"),
                    str(context_path),
                    "--task-type",
                    "appraisal",
                    "--risk-class",
                    "high",
                    "--packs",
                    str(packs),
                    "--out",
                    str(out_path),
                    "--created-at-utc",
                    TIMESTAMP,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            route = json.loads(out_path.read_text(encoding="utf-8"))
            validate_document(route, "domain_routing_decision")
            self.assertEqual(route["status"], "abstained")


if __name__ == "__main__":
    unittest.main()
