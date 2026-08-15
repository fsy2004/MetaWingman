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
from metawingman_core.server_handoff import (  # noqa: E402
    build_server_commands,
    build_server_handoff,
    materialize_server_handoff,
    validate_server_handoff_manifest,
)
from metawingman_core.training_corpus import (  # noqa: E402
    TrainingCorpusError,
    audit_training_dataset,
    build_training_examples,
    build_component_training_job,
    build_retrieval_pairs,
    build_training_plan,
    build_training_run_plan,
    classify_biomedical_stratum,
    fetch_training_plan,
    preflight_component_training,
)
from run_component_training import validate_training_job  # noqa: E402


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


def retrieval_example(index: int, split: str, family: str, record: str) -> dict[str, object]:
    text = f"Section title: Search strategy {index}\n\nMEDLINE search passage {index}"
    source_hash = hashlib.sha256(text.split("\n\n", 1)[1].encode()).hexdigest()
    example = {
        "schema_version": "1.0",
        "example_id": f"example:{index:020x}",
        "document_id": f"training-document:PMC{index}",
        "record_id": record,
        "family_id": family,
        "split": split,
        "task": "evidence_retrieval",
        "instruction": "Identify the source passage that supports the review workflow field: search.",
        "input_text": text,
        "target": {"section_role": "search", "section_title": f"Search strategy {index}"},
        "evidence_anchor": {
            "artifact_sha256": f"{index:064x}",
            "section_path": f"//body//sec[{index}]",
            "section_index": index,
            "source_text_sha256": source_hash,
        },
        "label_status": "deterministic_weak_supervision_requires_independent_validation",
        "gold_label": False,
    }
    body = json.dumps(example, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    example["content_sha256"] = hashlib.sha256(body).hexdigest()
    return example


def component_job_fixture(root: Path) -> dict[str, object]:
    for name, content in (("run-plan.json", "{}\n"), ("examples.jsonl", "{}\n"), ("pairs.jsonl", "{}\n"), ("training.lock", "torch==2.13.0\n")):
        (root / name).write_text(content, encoding="utf-8")
    digest = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    return {
        "schema_version": "1.0",
        "job_id": "fixture-component-job",
        "created_at_utc": TIMESTAMP,
        "component": "evidence_retrieval",
        "status": "ready_for_server_preflight",
        "reason_codes": [],
        "model": {
            "repository_id": "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
            "revision": "e1354b7a3a09615f6aba48dfad4b7a613eef7062",
            "tokenizer_revision": "e1354b7a3a09615f6aba48dfad4b7a613eef7062",
            "model_card_url": "https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext",
            "declared_license": "mit",
            "release_intent": "internal_research_only",
        },
        "dataset": {
            "run_plan_path": "run-plan.json", "run_plan_sha256": digest("run-plan.json"),
            "examples_path": "examples.jsonl", "examples_sha256": digest("examples.jsonl"),
            "pairs_path": "pairs.jsonl", "pairs_sha256": digest("pairs.jsonl"),
            "train_examples": 2, "development_examples": 2,
            "train_pairs": 2, "development_pairs": 2,
            "family_isolation": True, "label_policy": "weak_candidates_not_gold",
            "release_status": "raw_text_redistribution_forbidden_weights_pending_license_review",
        },
        "optimization": {"epochs": 2, "batch_size": 8, "learning_rate": 2e-5, "weight_decay": 0.01, "warmup_ratio": 0.1, "precision": "bf16", "selection_metric": "retrieval_recall_at_10"},
        "resources": {"cpu_cores": 8, "ram_gib": 32, "gpu_count": 1, "gpu_memory_gib_each": 24, "storage_gib": 100, "network_required": True},
        "output": {"root": "output", "checkpoint_every_steps": 100, "maximum_checkpoints": 2, "resume_checkpoint_hashes": []},
        "runtime": {"lock_path": "training.lock", "lock_sha256": digest("training.lock"), "python": "3.12", "cuda_required": True},
        "seed": 11,
        "command_argv": ["python", "metawingman/scripts/run_component_training.py"],
    }


class ReproducibleTrainingCorpusTests(unittest.TestCase):
    def test_handoff_normalizes_windows_member_paths_for_linux(self) -> None:
        result = build_server_handoff({
            "handoff_id": "portable-handoff",
            "created_at_utc": TIMESTAMP,
            "members": [r".\validation-output\training-corpus\jobs\retrieval.json"],
            "member_contents": {"validation-output/training-corpus/jobs/retrieval.json": "{}"},
            "component_job_ids": ["fixture-component-job"],
            "preflight": {"scientific_blockers": [], "server_checks_pending": []},
            "commands": {key: [key] for key in (
                "download", "freeze_base", "freeze", "audit", "export",
                "preflight", "train", "benchmark"
            )},
        })
        self.assertEqual(
            result["members"],
            ["validation-output/training-corpus/jobs/retrieval.json"],
        )
        self.assertNotIn("\\", result["members"][0])

    def test_handoff_commands_use_python_and_materialized_member_paths(self) -> None:
        commands = build_server_commands(
            "research/training-corpus-plan-biomedical-v2.json",
            "validation-output/training-corpus/jobs/evidence-retrieval.json",
        )
        self.assertTrue(all(argv[0] == "python" for argv in commands.values()))
        self.assertIn(
            "research/training-corpus-plan-biomedical-v2.json",
            commands["download"],
        )
        self.assertIn(
            "validation-output/training-corpus/jobs/evidence-retrieval.json",
            commands["train"],
        )

    def test_handoff_hash_index_must_exactly_match_members(self) -> None:
        result = build_server_handoff({
            "handoff_id": "hash-index-handoff", "created_at_utc": TIMESTAMP,
            "members": ["research/training-corpus-plan-biomedical-v2.json"],
            "member_contents": {"research/training-corpus-plan-biomedical-v2.json": "{}"},
            "component_job_ids": ["job"],
            "preflight": {"scientific_blockers": []},
            "commands": build_server_commands(
                "research/training-corpus-plan-biomedical-v2.json",
                "validation-output/training-corpus/jobs/evidence-retrieval.json",
            ),
        })
        result["member_hashes"] = {"wrong-member.json": "0" * 64}
        with self.assertRaises(TrainingCorpusError):
            validate_server_handoff_manifest(result)

    def test_handoff_refuses_to_materialize_over_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with self.assertRaises(TrainingCorpusError):
                materialize_server_handoff(root, root, [], {})

    def test_handoff_refuses_unmanaged_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            output = root / "handoff"
            output.mkdir()
            (output / "unmanaged.txt").write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(TrainingCorpusError):
                materialize_server_handoff(root, output, [], {})

    def test_handoff_excludes_full_text_secrets_and_checkpoints(self) -> None:
        result = build_server_handoff({
            "handoff_id": "fixture-handoff",
            "created_at_utc": TIMESTAMP,
            "members": [
                "research/training-corpus-plan-biomedical-v2.json",
                "validation-output/training-corpus/jobs/retrieval.json",
                "metawingman/references/dependencies/python-training.lock.txt",
            ],
            "member_contents": {
                "research/training-corpus-plan-biomedical-v2.json": "{}",
                "validation-output/training-corpus/jobs/retrieval.json": "{}",
                "metawingman/references/dependencies/python-training.lock.txt": "torch==2.13.0",
            },
            "component_job_ids": ["fixture-component-job"],
            "preflight": {"ready": False, "scientific_blockers": [], "server_checks_pending": ["server_hardware_unverified"]},
            "storage_estimate_gib": 500,
            "commands": {
                **build_server_commands(
                    "research/training-corpus-plan-biomedical-v2.json",
                    "validation-output/training-corpus/jobs/retrieval.json",
                ),
            },
        })
        members = set(result["members"])
        self.assertFalse(any(name.endswith((".pdf", ".xml", ".env", ".pt", ".safetensors")) for name in members))
        self.assertEqual(result["commands"]["download"][0], "python")

    def test_handoff_refuses_scientific_preflight_failure(self) -> None:
        with self.assertRaises(TrainingCorpusError):
            build_server_handoff({
                "handoff_id": "blocked-handoff", "created_at_utc": TIMESTAMP,
                "members": ["research/training-corpus-plan-biomedical-v2.json"], "component_job_ids": ["job"],
                "preflight": {"ready": False, "blocking_reasons": ["dataset_hash_mismatch"]},
                "commands": {},
            })

    def test_handoff_rejects_secret_like_metadata(self) -> None:
        with self.assertRaises(TrainingCorpusError):
            build_server_handoff({
                "handoff_id": "secret-handoff", "created_at_utc": TIMESTAMP,
                "members": ["research/training-corpus-plan-biomedical-v2.json"],
                "member_contents": {"research/training-corpus-plan-biomedical-v2.json": "{}"},
                "component_job_ids": ["job"], "preflight": {"scientific_blockers": []},
                "commands": {
                    **build_server_commands(
                        "research/training-corpus-plan-biomedical-v2.json",
                        "validation-output/training-corpus/jobs/retrieval.json",
                    ),
                    "benchmark": ["python", "metawingman/scripts/evaluate_pipeline.py", "api_key=sk-1234567890abcdef"],
                },
            })

    def test_hard_negative_never_crosses_split_or_reuses_family(self) -> None:
        examples = [
            retrieval_example(1, "train", "family:0000000000000001", "epmc:MED:1"),
            retrieval_example(2, "train", "family:0000000000000002", "epmc:MED:2"),
            retrieval_example(3, "development", "family:0000000000000003", "epmc:MED:3"),
            retrieval_example(4, "development", "family:0000000000000004", "epmc:MED:4"),
        ]
        strata = {
            item["record_id"]: {
                "primary_specialty": "oncology",
                "question_type": "harms",
            }
            for item in examples
        }
        pairs = build_retrieval_pairs(examples, strata, seed=11)
        self.assertTrue(any(pair["label"] == 0 for pair in pairs))
        for pair in pairs:
            self.assertEqual(pair["query_split"], pair["document_split"])
            validate_document(pair, "training_pair")
            if pair["label"] == 0:
                self.assertNotEqual(pair["query_family_id"], pair["document_family_id"])
                self.assertTrue(pair["shared_medical_neighborhood"])

    def test_preflight_blocks_mutable_model_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = component_job_fixture(root)
            job["model"]["revision"] = "main"
            report = preflight_component_training(job, root)
            self.assertFalse(report["ready"])
            self.assertIn("model_revision_not_immutable", report["reason_codes"])

    def test_training_runner_validate_only_never_imports_ml_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = component_job_fixture(root)
            with patch.dict(sys.modules, {"torch": None, "transformers": None}):
                report = validate_training_job(job, root)
            self.assertTrue(report["manifest_valid"])
            self.assertFalse(report["training_started"])

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
            job_path = "validation-output/training-corpus/jobs/section-role.json"
            job_run_plan = json.loads(json.dumps(run_plan))
            job_run_plan["dataset"]["train_examples"] = 3
            job_run_plan["dataset"]["development_examples"] = 1
            run_plan_path.write_text(json.dumps(job_run_plan), encoding="utf-8")
            job = build_component_training_job(
                job_run_plan,
                "section_role_classification",
                {
                    "repository_id": "example/model",
                    "revision": "a" * 40,
                    "tokenizer_revision": "b" * 40,
                    "model_card_url": "https://example.org/model",
                    "declared_license": "mit",
                },
                {
                    "epochs": 1, "batch_size": 2, "learning_rate": 2e-5,
                    "weight_decay": 0.01, "warmup_ratio": 0.1,
                    "precision": "fp32", "selection_metric": "macro_f1",
                },
                {
                    "cpu_cores": 2, "ram_gib": 4, "gpu_count": 0,
                    "gpu_memory_gib_each": 0, "storage_gib": 10,
                    "network_required": False,
                },
                TIMESTAMP,
                run_plan_path=run_plan_path.as_posix(),
                run_plan_sha256=hashlib.sha256(run_plan_path.read_bytes()).hexdigest(),
                job_path=job_path,
                runtime_lock_sha256="c" * 64,
            )
            self.assertEqual(job["command_argv"], [
                "python", "metawingman/scripts/run_component_training.py",
                job_path, "--root", ".",
            ])

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
