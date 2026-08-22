from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.run_agent_distillation_training import deterministic_split, load_training_examples


class AgentDistillationTrainingTests(unittest.TestCase):
    def test_readiness_and_stage_gate_training_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            examples = [{
                "example_id": f"e-{index}", "canonical_stage": "protocol_registration",
                "training_disposition": "positive_demonstration",
                "target_action": {"type": "compile_eligibility_criteria" if index < 4 else "compile_synthesis_plan"},
            } for index in range(8)]
            export = root / "export.json"; export.write_text(json.dumps({"examples": examples}))
            readiness = root / "ready.json"; readiness.write_text(json.dumps({
                "ready_for_student_training": True, "blockers": [],
                "eligible_example_ids": [row["example_id"] for row in examples],
            }))
            loaded = load_training_examples(export, readiness)
            train, dev = deterministic_split(loaded)
            self.assertEqual(len(train) + len(dev), 8)
            self.assertEqual(len(dev), 2)

    def test_blocked_readiness_refuses_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root / "export.json"; export.write_text(json.dumps({"examples": []}))
            readiness = root / "ready.json"; readiness.write_text(json.dumps({"ready_for_student_training": False, "blockers": ["blocked"]}))
            with self.assertRaisesRegex(ValueError, "readiness"):
                load_training_examples(export, readiness)


if __name__ == "__main__":
    unittest.main()
