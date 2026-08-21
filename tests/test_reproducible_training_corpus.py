from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "metawingman/scripts"))

import build_server_training_handoff  # noqa: E402
import prepare_component_training  # noqa: E402
import prepare_independent_validation_sample  # noqa: E402
import run_ai_only_pilot  # noqa: E402
import run_component_training  # noqa: E402
from metawingman_core.schema_guard import SchemaValidationError, validate_document  # noqa: E402
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
    _retrieval_query,
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


def training_run_plan_fixture() -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "run_plan_id": "fixture-training-run",
        "created_at_utc": TIMESTAMP,
        "dataset": {
            "manifest_path": "manifest.json",
            "manifest_sha256": "1" * 64,
            "examples_path": "examples.jsonl",
            "examples_sha256": "2" * 64,
            "train_examples": 2,
            "development_examples": 2,
            "held_out_examples": 0,
            "pairs_path": "pairs.jsonl",
            "pairs_sha256": "3" * 64,
            "train_pairs": 2,
            "development_pairs": 2,
            "biomedical_strata_counts": {"oncology|intervention": 4},
        },
        "model_contract": {
            "provider_neutral": True,
            "base_model": None,
            "revision": None,
            "tokenizer_revision": None,
            "license_review_required_before_training": True,
        },
        "objectives": ["section_role_classification", "evidence_retrieval"],
        "evaluation": {
            "unit": "review_family",
            "metrics": ["macro_f1", "retrieval_recall_at_k"],
            "selection_uses_development_only": True,
            "scientific_claims_disabled": True,
        },
        "contamination_controls": {
            "family_isolation": True,
            "journal_feature_forbidden": True,
            "published_answer_is_not_oracle": True,
            "model_memory_risk_recorded": True,
        },
        "objective_readiness": {
            "section_role_classification": "ready_for_server_preflight",
            "evidence_retrieval": "ready_for_server_preflight",
        },
        "execution_state": "ready_for_server_preflight",
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

    def test_handoff_includes_core_and_pdf_runtime_locks(self) -> None:
        for relative in build_server_training_handoff.SERVER_RUNTIME_LOCKS:
            self.assertTrue((ROOT / relative).is_file(), relative)
        core = (
            ROOT / "metawingman/references/dependencies/python-core.lock.txt"
        ).read_text(encoding="utf-8")
        pdf = (
            ROOT / "metawingman/references/dependencies/python-pdf.lock.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("jsonschema", core)
        self.assertIn("PyMuPDF", pdf)

    def test_warmup_ratio_materializes_as_warmup_steps(self) -> None:
        self.assertEqual(run_component_training._warmup_steps(5984, 16, 3, 0.1), 112)
        self.assertEqual(run_component_training._warmup_steps(10, 16, 1, 0.0), 0)
        self.assertEqual(run_component_training._warmup_steps(100, 16, 2, 0.1), 1)

    def test_rank_metrics_masks_same_family_and_ranks_own_document(self) -> None:
        similarities = [
            [1.0, 0.5, 0.9],
            [0.4, 1.0, 0.3],
            [0.2, 0.1, 1.0],
        ]
        families = ["family:a", "family:b", "family:a"]
        result = run_component_training._rank_metrics(similarities, families)
        self.assertEqual(result["precision_at_1"], 1.0)
        self.assertEqual(result["recall_at_10"], 1.0)
        self.assertAlmostEqual(result["mrr"], 1.0)

    def test_rank_metrics_penalizes_missed_top_rank(self) -> None:
        similarities = [[0.5, 1.0], [1.0, 0.5]]
        families = ["family:a", "family:b"]
        result = run_component_training._rank_metrics(similarities, families)
        self.assertAlmostEqual(result["mrr"], 0.5)
        self.assertEqual(result["precision_at_1"], 0.0)
        self.assertEqual(result["recall_at_10"], 1.0)

    def test_hard_negative_batching_preserves_pair_order_scores_and_metrics(self) -> None:
        pairs = [
            {"pair_id": "pair-20", "query_example_id": "query-b", "query_split": "development", "query_text": "beta query", "document_example_id": "shared-document", "document_text": "shared document", "label": 1},
            {"pair_id": "pair-21", "query_example_id": "query-b", "query_split": "development", "query_text": "beta query", "document_example_id": "beta-negative", "document_text": "beta negative", "label": 0},
            {"pair_id": "pair-10", "query_example_id": "query-a", "query_split": "development", "query_text": "alpha query", "document_example_id": "shared-document", "document_text": "shared document", "label": 1},
            {"pair_id": "pair-11", "query_example_id": "query-a", "query_split": "development", "query_text": "alpha query", "document_example_id": "alpha-negative", "document_text": "alpha negative", "label": 0},
            {"pair_id": "ignored-train", "query_example_id": "query-train", "query_split": "train", "query_text": "train query", "document_example_id": "train-document", "document_text": "train document", "label": 1},
        ]
        vectors = {
            "beta query": (1.0, 0.0),
            "alpha query": (0.0, 1.0),
            "shared document": (0.8, 0.6),
            "beta negative": (0.8, 0.6),
            "alpha negative": (0.0, 1.0),
        }
        encode_calls: list[tuple[list[str], int]] = []

        def encode(texts: list[str], max_length: int) -> list[tuple[float, float]]:
            encode_calls.append((list(texts), max_length))
            return [vectors[text] for text in texts]

        def paired_cosine(
            query_vectors: list[tuple[float, float]],
            document_vectors: list[tuple[float, float]],
            query_indexes: list[int],
            document_indexes: list[int],
        ) -> list[float]:
            return [
                sum(left * right for left, right in zip(query_vectors[query_index], document_vectors[document_index]))
                for query_index, document_index in zip(query_indexes, document_indexes)
            ]

        development_pairs, batched_scores = run_component_training._batched_candidate_scores(
            pairs, encode, paired_cosine
        )
        legacy_scores = [
            sum(left * right for left, right in zip(vectors[item["query_text"]], vectors[item["document_text"]]))
            for item in pairs
            if item["query_split"] == "development"
        ]
        self.assertEqual([item["pair_id"] for item in development_pairs], ["pair-20", "pair-21", "pair-10", "pair-11"])
        self.assertEqual(batched_scores, legacy_scores)
        self.assertEqual(
            encode_calls,
            [
                (["beta query", "alpha query"], 256),
                (["shared document", "beta negative", "alpha negative"], 512),
            ],
        )
        self.assertEqual(
            run_component_training._hard_negative_metrics(development_pairs, batched_scores),
            {"mrr": 0.75, "precision_at_1": 0.5},
        )

    def test_pad_id_lists_pads_to_batch_maximum(self) -> None:
        padded, masks = run_component_training._pad_id_lists([[1, 2], [3], []], 0)
        self.assertEqual(padded, [[1, 2], [3, 0], [0, 0]])
        self.assertEqual(masks, [[1, 1], [1, 0], [0, 0]])
        self.assertEqual(run_component_training._pad_id_lists([], 0), ([], []))

    def test_accumulation_steps_defaults_to_one_when_field_absent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = component_job_fixture(root)
            self.assertNotIn("gradient_accumulation_steps", job["optimization"])
            self.assertEqual(run_component_training._accumulation_steps(job), 1)
            job["optimization"]["gradient_accumulation_steps"] = 2
            self.assertEqual(run_component_training._accumulation_steps(job), 2)

    def test_accumulation_windows_partition_batches_and_keep_partial_tail(self) -> None:
        self.assertEqual(
            run_component_training._accumulation_windows(6, 1),
            [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1)],
        )
        self.assertEqual(
            run_component_training._accumulation_windows(6, 2),
            [(0, 2), (2, 2), (4, 2)],
        )
        self.assertEqual(
            run_component_training._accumulation_windows(5, 2),
            [(0, 2), (2, 2), (4, 1)],
        )

    def test_accumulation_averages_synthetic_micro_batch_losses(self) -> None:
        step_losses = [2.0, 4.0, 3.0, 1.0, 5.0]
        self.assertEqual(run_component_training._accumulate_losses(step_losses, 1), step_losses)
        self.assertEqual(
            run_component_training._accumulate_losses(step_losses, 2),
            [3.0, 2.0, 5.0],
        )

    def test_job_schema_accepts_gradient_accumulation_steps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = component_job_fixture(root)
            validate_document(job, "component_training_job")
            job["optimization"]["gradient_accumulation_steps"] = 2
            validate_document(job, "component_training_job")
            job["optimization"]["gradient_accumulation_steps"] = 0
            with self.assertRaises(SchemaValidationError):
                validate_document(job, "component_training_job")

    def _run_prepare_component_training(self, root: Path, extra_args: list[str]) -> dict[str, object]:
        run_plan_path = root / "run-plan.json"
        runtime_lock_path = root / "training.lock"
        output_path = root / "job.json"
        run_plan_path.write_text(json.dumps(training_run_plan_fixture()), encoding="utf-8")
        runtime_lock_path.write_text("torch==2.13.0\n", encoding="utf-8")
        argv = [
            "prepare_component_training.py",
            str(run_plan_path),
            "--component", "evidence_retrieval",
            "--model-repository", "example/model",
            "--model-revision", "a" * 40,
            "--tokenizer-revision", "b" * 40,
            "--model-card-url", "https://example.org/model",
            "--model-license", "mit",
            "--runtime-lock", str(runtime_lock_path),
            "--output-root", "training-output",
            "--out", str(output_path),
            "--created-at-utc", TIMESTAMP,
            *extra_args,
        ]
        with patch.object(sys, "argv", argv):
            self.assertEqual(prepare_component_training.main(), 0)
        return json.loads(output_path.read_text(encoding="utf-8"))

    def test_prepare_component_training_defaults_gradient_accumulation_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = self._run_prepare_component_training(Path(directory), [])
        self.assertEqual(job["optimization"]["gradient_accumulation_steps"], 1)

    def test_prepare_component_training_plumbs_explicit_gradient_accumulation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = self._run_prepare_component_training(
                Path(directory), ["--gradient-accumulation-steps", "4"]
            )
        self.assertEqual(job["optimization"]["gradient_accumulation_steps"], 4)

    def test_prepare_component_training_rejects_zero_gradient_accumulation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stderr = io.StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as raised:
                self._run_prepare_component_training(root, ["--gradient-accumulation-steps", "0"])
        self.assertEqual(raised.exception.code, 2)
        self.assertIn("must be >= 1", stderr.getvalue())

    def test_request_bytes_enforces_wall_clock_deadline_on_slow_drip(self) -> None:
        from metawingman_core import training_corpus as corpus_module

        class DripResponse:
            def read(self, size: int) -> bytes:
                return b"x" * 1024

            def geturl(self) -> str:
                return "https://example.org/slow"

            def __enter__(self) -> "DripResponse":
                return self

            def __exit__(self, *_: object) -> bool:
                return False

        class Opener:
            def open(self, _request: object, timeout: float) -> DripResponse:
                return DripResponse()

        clock = {"now": 0.0}

        def advancing_clock() -> float:
            clock["now"] += 30.0
            return clock["now"]

        with patch.object(corpus_module, "public_https_opener", return_value=Opener()), \
            patch.object(corpus_module, "validate_public_https_url", side_effect=lambda value: value), \
            patch.object(corpus_module.time, "monotonic", side_effect=advancing_clock):
            with self.assertRaisesRegex(TrainingCorpusError, "wall-clock deadline"):
                corpus_module._request_bytes("https://example.org/slow", max_bytes=40 * 1024 * 1024)

    def test_retrieval_query_includes_review_title_when_available(self) -> None:
        example = retrieval_example(1, "train", "family:0000000000000001", "epmc:0000000000000001")
        example["review_title"] = "Antibiotics for chronic wounds: a meta-analysis"
        query = _retrieval_query(example)
        self.assertIn("Antibiotics for chronic wounds", query)
        self.assertIn(example["instruction"], query)
        without_title = retrieval_example(1, "train", "family:0000000000000001", "epmc:0000000000000001")
        self.assertEqual(_retrieval_query(without_title), without_title["instruction"])

    def _pilot_fixture(self):
        examples = [
            retrieval_example(i, "development", f"family:{i:08x}", f"epmc:{i:08x}")
            for i in range(30)
        ]
        for index, example in enumerate(examples):
            example["review_title"] = f"Review title {index}"
        section_role = [dict(example, task="section_role_classification") for example in examples[:10]]
        all_examples = examples + section_role
        pairs = [
            {
                "pair_id": f"p-pos-{example['example_id']}",
                "query_example_id": example["example_id"],
                "query_split": "development",
                "label": 1,
                "query_text": _retrieval_query(example),
                "document_text": example["input_text"],
                "document_example_id": example["example_id"],
            }
            for example in examples
        ]
        return all_examples, pairs

    def test_pilot_task_building_is_deterministic(self) -> None:
        all_examples, pairs = self._pilot_fixture()
        first = run_ai_only_pilot.build_pilot_tasks(all_examples, pairs, "C0", sample_size=20, seed=7)
        second = run_ai_only_pilot.build_pilot_tasks(all_examples, pairs, "C0", sample_size=20, seed=7)
        self.assertEqual([task["task_id"] for task in first], [task["task_id"] for task in second])
        section_role = [task for task in first if task["task_id"].startswith("sr-")]
        retrieval = [task for task in first if task["task_id"].startswith("rt-")]
        self.assertEqual(len(section_role), 10)
        self.assertEqual(len(retrieval), 20)
        with_verifier = run_ai_only_pilot.build_pilot_tasks(
            all_examples, pairs, "C3", sample_size=5, seed=7,
            verifier_predictions={example["example_id"]: {"section_role": "search"} for example in all_examples},
        )
        for task in with_verifier:
            field = "verifier_prediction" if task["task_id"].startswith("sr-") else "verifier_ranking"
            self.assertIn(field, task["input_document"])

    def test_pilot_scoring_assigns_perfect_scores_to_perfect_runs(self) -> None:
        all_examples, pairs = self._pilot_fixture()
        tasks = run_ai_only_pilot.build_pilot_tasks(all_examples, pairs, "C0", sample_size=10, seed=7)
        section_role_by_id = {
            example["example_id"]: example
            for example in all_examples
            if example["task"] == "section_role_classification"
        }
        runs = []
        for task in tasks:
            if task["task_id"].startswith("sr-"):
                example_id = "example:" + task["task_id"].rsplit("-", 1)[-1]
                runs.append({
                    "task_id": task["task_id"],
                    "status": "candidate_generated",
                    "candidate": {"section_role": section_role_by_id[example_id]["target"]["section_role"]},
                    "attempts": 1,
                    "usage_totals": {"total_tokens": 10},
                })
            else:
                runs.append({
                    "task_id": task["task_id"],
                    "status": "candidate_generated",
                    "candidate": {"selected_index": 0},
                    "attempts": 1,
                    "usage_totals": {"total_tokens": 10},
                })
        scoring = run_ai_only_pilot.score_pilot_tasks(runs, all_examples, pairs)
        self.assertEqual(scoring["section_role"]["macro_f1"], 1.0)
        self.assertEqual(scoring["retrieval"]["mrr"], 1.0)
        self.assertEqual(scoring["retrieval"]["precision_at_1"], 1.0)
        self.assertEqual(scoring["cost"]["provider_calls"], len(tasks))

    def test_validation_sample_is_stratified_blind_and_deterministic(self) -> None:
        total = 240
        examples = []
        plan_records = []
        for index in range(total):
            specialty = f"spec-{index % 24}"
            question = f"qt-{index % 3}"
            record_id = f"epmc:{index:08x}"
            examples.append(retrieval_example(index, "development", f"family:{index:08x}", record_id))
            plan_records.append({
                "record_id": record_id,
                "pmcid": f"PMC{index}",
                "biomedical_stratum": {
                    "primary_specialty": specialty,
                    "question_type": question,
                    "sampling_key": f"{specialty}|{question}",
                },
            })
        plan = {"records": plan_records}
        blind, key, summary = prepare_independent_validation_sample.build_validation_sample(
            examples, plan, target_records=200, minimum_strata=20, seed=7,
        )
        self.assertGreaterEqual(summary["selected_records"], 200)
        self.assertGreaterEqual(summary["strata_covered"], 20)
        for row in blind:
            self.assertNotIn("biomedical_stratum", json.dumps(row))
            self.assertIn("record_id", row)
        blind_again, _, _ = prepare_independent_validation_sample.build_validation_sample(
            examples, plan, target_records=200, minimum_strata=20, seed=7,
        )
        self.assertEqual(blind, blind_again)
        self.assertEqual(key[0]["record_id"], blind[0]["record_id"])

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
        self.assertEqual(
            result["content_policy"]["secret_scan_status"],
            "passed_bounded_patterns_not_proof_of_absence",
        )

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

    def test_skip_pdf_fetches_xml_only_and_marks_complete(self) -> None:
        plan = fixture_plan(1)
        xml = b"<article><body><sec><title>Search methods</title><p>" + b"x" * 300 + b"</p></sec></body></article>"
        pdf_attempts: list[str] = []

        def request(url: str, **_: object) -> tuple[bytes, str]:
            pdf_attempts.append(url)
            return xml, url

        with tempfile.TemporaryDirectory() as directory, \
            patch("metawingman_core.training_corpus._oa_license", return_value=("CC BY", "verified_not_retracted")), \
            patch("metawingman_core.training_corpus._full_text_urls", side_effect=AssertionError("pdf lookup must be skipped")), \
            patch("metawingman_core.training_corpus._request_bytes", side_effect=request), \
            patch("metawingman_core.training_corpus._parser_metrics", return_value=dict(ZERO_METRICS)):
            manifest = fetch_training_plan(
                plan, Path(directory), manifest_id="fixture-manifest", delay_seconds=0,
                created_at_utc=TIMESTAMP, skip_pdf=True,
            )
            self.assertEqual(manifest["summary"]["complete"], 1)
            self.assertEqual(manifest["summary"]["xml_files"], 1)
            self.assertEqual(manifest["summary"]["pdf_files"], 0)
            self.assertEqual(len(pdf_attempts), 1)
            self.assertTrue(pdf_attempts[0].endswith("fullTextXML"))

    def test_bucketed_negative_mining_respects_medical_neighborhood(self) -> None:
        examples = []
        for index in range(12):
            example = retrieval_example(index, "train", f"family:{index:08x}", f"epmc:{index:08x}")
            example["input_text"] = f"shared passage token {index} " * 20
            examples.append(example)
        strata = {
            f"epmc:{index:08x}": {
                "primary_specialty": "oncology" if index < 6 else "neurology",
                "question_type": "intervention" if index % 2 == 0 else "diagnostic",
            }
            for index in range(12)
        }
        pairs = build_retrieval_pairs(examples, strata, seed=11)
        negatives = [pair for pair in pairs if pair["label"] == 0]
        self.assertTrue(negatives)
        self.assertTrue(all(pair["shared_medical_neighborhood"] for pair in negatives))
        for pair in negatives:
            query_stratum = strata[pair["query_record_id"]]
            document_stratum = strata[pair["document_record_id"]]
            same_specialty = query_stratum["primary_specialty"] == document_stratum["primary_specialty"]
            same_question = query_stratum["question_type"] == document_stratum["question_type"]
            self.assertTrue(same_specialty or same_question)
            expected = []
            if same_specialty:
                expected.append("primary_specialty")
            if same_question:
                expected.append("question_type")
            self.assertEqual(pair["neighborhood_keys"], expected)

    def test_overlap_lookup_matches_pure_python_formula(self) -> None:
        from metawingman_core import training_corpus as corpus_module

        retrieval = [
            retrieval_example(index, "train", f"family:{index:08x}", f"epmc:{index:08x}")
            for index in range(12)
        ]
        for index, example in enumerate(retrieval):
            example["input_text"] = f"the shared passage token {index} " * 20
        document_token_sets = {
            example["example_id"]: corpus_module._tokens(example["input_text"])
            for example in retrieval
        }
        lookup = corpus_module._build_overlap_lookup(retrieval, document_token_sets)
        candidate_ids = [example["example_id"] for example in retrieval]
        for example in retrieval:
            query_tokens = corpus_module._tokens(example["instruction"] + " " + example["input_text"])
            expected = {
                identifier: len(query_tokens & document_token_sets[identifier])
                for identifier in candidate_ids
            }
            self.assertEqual(lookup(query_tokens, candidate_ids), expected)

    def test_vectorized_pair_selection_matches_python_fallback(self) -> None:
        from unittest.mock import patch

        from metawingman_core import training_corpus as corpus_module

        examples = []
        for index in range(16):
            example = retrieval_example(index, "train", f"family:{index // 2:08x}", f"epmc:{index:08x}")
            # Shared passages force token-overlap ties so the sha256 tie-break is
            # exercised, and families are shared to exercise the family filter.
            example["input_text"] = f"Section title: S{index}\n\nshared passage token {index % 3}"
            example["evidence_anchor"]["source_text_sha256"] = hashlib.sha256(f"src{index}".encode()).hexdigest()
            examples.append(example)
        strata = {
            f"epmc:{index:08x}": {
                "primary_specialty": "oncology" if index < 8 else "neurology",
                "question_type": "intervention" if index % 2 == 0 else "diagnostic",
            }
            for index in range(16)
        }
        vectorized = build_retrieval_pairs(examples, strata, seed=11)
        with patch.object(corpus_module, "_build_token_matrix", return_value=None):
            fallback = build_retrieval_pairs(examples, strata, seed=11)
        self.assertEqual(vectorized, fallback)
        self.assertEqual([pair["pair_id"] for pair in vectorized], [pair["pair_id"] for pair in fallback])

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
