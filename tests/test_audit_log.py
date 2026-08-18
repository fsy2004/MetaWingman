"""Tests for the audit log + meta-update loop."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "metawingman" / "scripts"))

from record_audit_log import append_entry, apply_entry, build_entry, list_open, load_entries  # noqa: E402


def make_entry(stage: str = "appraisal", event: str = "failure") -> dict:
    return build_entry(
        stage=stage,
        event_type=event,
        description="unanchored RoB signal",
        evidence_source="tests/test_appraisal_step_verifier.py:45",
        proposed_update={
            "target_file": "references/socratic-checklists/appraisal.json",
            "section": "appraisal-02",
            "new_text": "require anchors",
            "rationale": "unanchored judgments unreproducible",
            "source": "Cochrane Handbook v6 Ch.8",
        },
    )


class AuditLogTests(unittest.TestCase):
    def test_entry_roundtrip_and_open_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            entry = make_entry()
            append_entry(log, entry)
            loaded = load_entries(log)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["entry_id"], entry["entry_id"])
            self.assertEqual(len(list_open(loaded)), 1)

    def test_apply_marks_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            entry = make_entry()
            append_entry(log, entry)
            applied = apply_entry(log, entry["entry_id"], "abc123")
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["applied_commit"], "abc123")
            self.assertEqual(list_open(load_entries(log)), [])

    def test_apply_twice_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "audit.jsonl"
            entry = make_entry()
            append_entry(log, entry)
            apply_entry(log, entry["entry_id"], "c1")
            with self.assertRaises(ValueError):
                apply_entry(log, entry["entry_id"], "c2")

    def test_duplicate_entry_is_idempotent_by_fingerprint(self) -> None:
        first = make_entry()
        second = make_entry()
        self.assertEqual(first["entry_id"], second["entry_id"])

    def test_entry_passes_schema(self) -> None:
        entry = make_entry()
        self.assertEqual(entry["schema_version"], "1.0")
        self.assertTrue(entry["entry_id"].startswith("audit:"))


if __name__ == "__main__":
    unittest.main()
