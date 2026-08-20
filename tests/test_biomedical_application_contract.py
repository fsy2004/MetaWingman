from __future__ import annotations

import copy
import hashlib
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
        "eligible_study_designs": [],
        "population_constraints": [],
        "setting_constraints": [],
        "equity_constraints": [],
        "database_constraints": [],
        "terminology_releases": [],
        "source_classes": ["bibliographic_database"],
        "languages": ["en"],
        "geographies": [],
        "ood_assessment": {"status": "in_scope", "reason_codes": [], "routing_confidence": 1.0},
        "created_at_utc": TIMESTAMP,
        "updated_at_utc": TIMESTAMP,
    }


def domain_pack_fixture() -> dict[str, object]:
    return json.loads((PACK_DIR / "biomedical-foundation.json").read_text(encoding="utf-8"))


def copy_declared_authorities(pack_dir: Path, skill_root: Path) -> None:
    for pack_path in pack_dir.glob("*.json"):
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        for authority in pack["authority_sources"]:
            relative = Path(authority["path"])
            destination = skill_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((SKILL_ROOT / relative).read_bytes())


def initialize_review(root: Path, name: str = "Legacy Oncology Review") -> Path:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "init_review.py"),
            "--name",
            name,
            "--root",
            str(root),
            "--profile",
            "diagnostic",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(completed.stdout.strip())


def make_legacy(project: Path) -> None:
    context_path = project / "01_protocol/biomedical_context.json"
    if context_path.exists():
        context_path.unlink()
    (project / "10_benchmark/ai_only_evaluation_plan.json").unlink(missing_ok=True)
    project_path = project / "00_admin/project.json"
    project_document = json.loads(project_path.read_text(encoding="utf-8"))
    project_document.pop("scaffold_version", None)
    project_path.write_text(json.dumps(project_document, indent=2) + "\n", encoding="utf-8")


def run_migration(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "migrate_biomedical_context.py"),
            str(project),
            *arguments,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class BiomedicalApplicationContractTests(unittest.TestCase):
    def test_init_review_writes_declared_specialties_without_name_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_review.py"),
                    "--name",
                    "Oncology Imaging Review",
                    "--root",
                    temporary_directory,
                    "--profile",
                    "diagnostic",
                    "--specialty",
                    "diagnostics",
                    "--specialty",
                    "imaging",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            context = json.loads(
                (Path(completed.stdout.strip()) / "01_protocol/biomedical_context.json")
                .read_text(encoding="utf-8")
            )
            validate_document(context, "biomedical_context")
            self.assertEqual(context["primary_specialty"], "diagnostics")
            self.assertEqual(context["secondary_specialties"], ["imaging"])
            self.assertEqual(context["question_framework"]["source_text"], "")
            self.assertEqual(context["question_framework"]["normalized_concepts"], [])
            self.assertEqual(context["ood_assessment"]["status"], "uncertain")

    def test_migration_requires_explicit_specialty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = initialize_review(Path(temporary_directory))
            make_legacy(project)
            completed = run_migration(project)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("--specialty is required", completed.stderr)

    def test_migration_writes_context_and_profile_hash_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = initialize_review(Path(temporary_directory))
            make_legacy(project)
            profile_path = project / "01_protocol/review_profile.json"
            profile_hash = hashlib.sha256(profile_path.read_bytes()).hexdigest()

            completed = run_migration(
                project,
                "--specialty",
                "diagnostics",
                "--specialty",
                "imaging",
                "--created-at-utc",
                TIMESTAMP,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["status"], "migrated")
            self.assertEqual(result["profile_sha256"], profile_hash)
            context_path = project / "01_protocol/biomedical_context.json"
            context = json.loads(context_path.read_text(encoding="utf-8"))
            validate_document(context, "biomedical_context")
            self.assertEqual(context["primary_specialty"], "diagnostics")
            self.assertEqual(context["secondary_specialties"], ["imaging"])
            self.assertEqual(context["question_framework"]["source_text"], "")
            self.assertEqual(context["ood_assessment"]["status"], "uncertain")
            events = [
                json.loads(line)
                for line in (project / "00_admin/event_ledger.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(events[-1]["action_type"], "biomedical_context_migrated")
            self.assertEqual(events[-1]["input"]["sha256"], profile_hash)
            self.assertEqual(
                events[-1]["output"]["sha256"],
                hashlib.sha256(context_path.read_bytes()).hexdigest(),
            )

    def test_migration_dry_run_does_not_write_context_or_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = initialize_review(Path(temporary_directory))
            make_legacy(project)
            ledger_path = project / "00_admin/event_ledger.jsonl"
            ledger_before = ledger_path.read_bytes()

            completed = run_migration(
                project,
                "--specialty",
                "diagnostics",
                "--dry-run",
                "--created-at-utc",
                TIMESTAMP,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            proposed = json.loads(completed.stdout)
            validate_document(proposed, "biomedical_context")
            self.assertFalse((project / "01_protocol/biomedical_context.json").exists())
            self.assertEqual(ledger_path.read_bytes(), ledger_before)

    def test_migration_refuses_to_overwrite_existing_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = initialize_review(Path(temporary_directory))
            context_path = project / "01_protocol/biomedical_context.json"
            self.assertTrue(context_path.is_file())
            original = context_path.read_bytes()

            completed = run_migration(project, "--specialty", "diagnostics")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Refusing to overwrite existing biomedical context", completed.stderr)
            self.assertEqual(context_path.read_bytes(), original)

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

    def test_biomedical_coverage_cli_accepts_governed_live_packs(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "audit_biomedical_coverage.py"),
                "--packs",
                str(PACK_DIR),
                "--matrix",
                str(SKILL_ROOT / "references/system-capability-matrix.json"),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"], report["issues"])
        self.assertEqual(report["unsupported_combinations"], [])

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

    def test_high_risk_route_abstains_when_profile_is_contract_only(self) -> None:
        result = route_domain_packs(
            biomedical_context_fixture("diagnostic"),
            load_domain_packs(PACK_DIR),
            "appraisal",
            "high",
            TIMESTAMP,
        )
        self.assertEqual(result["status"], "abstained")
        self.assertIn("profile_not_fixture_tested", result["reason_codes"])

    def test_moderate_route_selects_foundation_then_contract_profile(self) -> None:
        result = route_domain_packs(
            biomedical_context_fixture("diagnostic"),
            load_domain_packs(PACK_DIR),
            "appraisal",
            "moderate",
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

    def test_authority_source_drift_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "metawingman"
            packs = root / "references" / "domain-packs"
            packs.mkdir(parents=True)
            for path in PACK_DIR.glob("*.json"):
                (packs / path.name).write_bytes(path.read_bytes())
            copy_declared_authorities(packs, root)
            load_domain_packs(packs)
            with (root / "references" / "methodology-source-registry.md").open("ab") as handle:
                handle.write(b"\ndrift")
            with self.assertRaises(BiomedicalDomainError):
                load_domain_packs(packs)

    def test_claim_bearing_schemas_reject_overclaim_states(self) -> None:
        stratum = {
            "schema_version": "1.0", "primary_specialty": "oncology", "secondary_specialties": [],
            "question_type": "harms", "study_designs": ["randomized_trial"],
            "synthesis_routes": ["pairwise"], "languages": ["en"],
            "document_modalities": ["abstract"], "challenge_tags": [],
            "sampling_key": "oncology|harms|randomized_trial|pairwise",
            "label_status": "gold", "evidence": ["model-output"],
        }
        with self.assertRaises(SchemaValidationError):
            validate_document(stratum, "biomedical_training_stratum")
        report = {
            "schema_version": "1.0", "report_id": "coverage-fixture", "registry_sha256": "1" * 64,
            "generated_at_utc": TIMESTAMP, "application_domain": APPLICATION_DOMAIN,
            "profiles": [], "specialties": [],
            "issues": [{"severity": "error", "code": "missing_evidence", "message": "fixture"}],
            "valid": True,
        }
        with self.assertRaises(SchemaValidationError):
            validate_document(report, "domain_coverage_report")

    def test_route_cli_writes_valid_abstention_and_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            context_path = root / "context.json"
            out_path = root / "route.json"
            packs = root / "metawingman" / "references" / "domain-packs"
            packs.mkdir(parents=True)
            context_path.write_text(json.dumps(biomedical_context_fixture("diagnostic")), encoding="utf-8")
            (packs / "biomedical-foundation.json").write_text(
                (PACK_DIR / "biomedical-foundation.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            copy_declared_authorities(packs, root / "metawingman")
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

    def test_routing_schema_rejects_incoherent_selected_state(self) -> None:
        route = route_domain_packs(
            biomedical_context_fixture("diagnostic"), load_domain_packs(PACK_DIR), "screening", "moderate", TIMESTAMP
        )
        route["selected_pack_ids"] = []
        route["fallback"] = {"action": "abstain", "pack_id": None}
        with self.assertRaises(SchemaValidationError):
            validate_document(route, "domain_routing_decision")

if __name__ == "__main__":
    unittest.main()
