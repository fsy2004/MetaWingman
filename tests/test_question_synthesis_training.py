from __future__ import annotations

import sys
import tempfile
import unittest
from unittest.mock import patch
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "metawingman" / "scripts"
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from metawingman_core.training_corpus import TrainingCorpusError
from metawingman_core.question_synthesis_training import export_question_synthesis_examples
from train_question_synthesis_component import validate_question_synthesis_job
from test_question_synthesis_benchmark import benchmark_case_fixture


TIMESTAMP = "2026-08-20T00:00:00Z"


class QuestionSynthesisTrainingTests(unittest.TestCase):
    def test_export_rejects_family_cross_split(self) -> None:
        development = benchmark_case_fixture()
        held_out = benchmark_case_fixture()
        held_out["case_id"] = "case-held-out"
        held_out["split"] = "held_out"
        with self.assertRaises(TrainingCorpusError):
            export_question_synthesis_examples(
                cases=[development, held_out], trajectories=[], created_at_utc=TIMESTAMP
            )

    def test_published_decision_is_not_named_gold(self) -> None:
        manifest = export_question_synthesis_examples(
            cases=[benchmark_case_fixture()], trajectories=[], created_at_utc=TIMESTAMP
        )
        self.assertEqual(
            {row["label_authority"] for row in manifest["examples"]},
            {"published_reference"},
        )

    def test_hard_negative_names_violated_rule(self) -> None:
        manifest = export_question_synthesis_examples(
            cases=[benchmark_case_fixture()], trajectories=[], created_at_utc=TIMESTAMP
        )
        negatives = [row for row in manifest["examples"] if row["target"]["label"] == 0]
        self.assertTrue(negatives)
        self.assertTrue(all(row["violated_rule"] for row in negatives))

    def test_validate_only_rejects_hash_drift_without_importing_ml_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            examples = root / "examples.jsonl"
            examples.write_text("{}\n", encoding="utf-8")
            job = {
                "component": "risk_cost_router",
                "status": "ready_for_server_preflight",
                "dataset": {
                    "examples_path": "examples.jsonl",
                    "examples_sha256": "0" * 64,
                },
            }
            with patch.dict(sys.modules, {"torch": None, "transformers": None, "sklearn": None}):
                with self.assertRaises(TrainingCorpusError):
                    validate_question_synthesis_job(job, root)


if __name__ == "__main__":
    unittest.main()
