import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class VerifierCounterfactualReplayTests(unittest.TestCase):
    def test_cli_replays_locked_outputs_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            operational = root / "operational.jsonl"
            raw = root / "raw.jsonl"
            outputs = root / "outputs"
            outputs.mkdir()
            operational.write_text(json.dumps({
                "id": "a", "cutoff_verification": {
                    "status": "passed", "conservative_latest_date": "2020-06-01"
                }
            }) + "\n", encoding="utf-8")
            raw.write_text(json.dumps({
                "id": "late", "first_publication_date": "2020-06-08", "title": "Later evidence"
            }) + "\n", encoding="utf-8")
            for configuration in ("generic-fixed-unverified", "conclusion-directed-unverified"):
                (outputs / f"{configuration}-1.json").write_text(
                    json.dumps({"proposed_candidate_ids": ["a"]}), encoding="utf-8"
                )
            lock = root / "acquisition.lock.json"
            lock.write_text(json.dumps({"status": "locked", "locked_slots": 12}), encoding="utf-8")
            lock_sha = hashlib.sha256(lock.read_bytes()).hexdigest()
            plan = root / "counterfactual-plan.json"
            plan.write_text(json.dumps({
                "schema_version": "1.0",
                "counterfactual_id": "verifier-unknown-postcutoff-v1",
                "frozen_at_utc": "2026-08-21T15:00:00Z",
                "registration_timing": "after_primary_scoring_before_counterfactual_replay",
                "source_lock_sha256": lock_sha,
                "historical_cutoff": "2020-06-07",
                "unknown_candidate_id": "counterfactual:unknown",
                "postcutoff_candidate_id": "late",
                "postcutoff_first_publication_date": "2020-06-08",
                "source_configurations": ["generic-fixed-unverified", "conclusion-directed-unverified"],
                "seeds": [1],
                "expected": {"unknown_rejected": 1, "postcutoff_rejected": 1, "baseline_verified_preserved": True},
                "provider_calls": 0
            }), encoding="utf-8")
            report = root / "report.json"
            script = Path(__file__).parents[1] / "metawingman" / "scripts" / "replay_acquisition_verifier_counterfactual.py"
            proc = subprocess.run([
                sys.executable, str(script), str(plan), "--source-lock", str(lock),
                "--operational-corpus", str(operational), "--raw-corpus", str(raw),
                "--source-outputs", str(outputs), "--out", str(report)
            ], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["provider_calls"], 0)
            self.assertEqual(len(payload["replays"]), 2)
            self.assertTrue(all(item["baseline_verified_preserved"] for item in payload["replays"]))


if __name__ == "__main__":
    unittest.main()
