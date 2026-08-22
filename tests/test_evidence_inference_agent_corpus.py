from __future__ import annotations

import csv
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.build_evidence_inference_agent_corpus import build_evidence_inference_corpus


class EvidenceInferenceCorpusTests(unittest.TestCase):
    def test_builds_majority_labels_with_exact_source_spans_and_family_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "fixture.tar.gz"
            annotation_fields = ["UserID", "PromptID", "PMCID", "Valid Label", "Valid Reasoning", "Label", "Annotations", "Label Code", "In Abstract", "Evidence Start", "Evidence End"]
            prompt_fields = ["PromptID", "PMCID", "Outcome", "Intervention", "Comparator"]
            annotations: list[dict[str, str]] = []
            prompts: list[dict[str, str]] = []
            documents: dict[str, str] = {}
            split_ids = {"train": ["1", "2"], "validation": ["3"], "test": ["4"]}
            for pmcid in ("1", "2", "3", "4"):
                prompt_id = f"P{pmcid}"
                evidence = "Treatment reduced mortality compared with placebo."
                text = f"Methods and results. {evidence} End."
                start = str(text.index(evidence)); end = str(start_int := text.index(evidence) + len(evidence))
                self.assertEqual(text[int(start):start_int], evidence)
                documents[pmcid] = text
                prompts.append({"PromptID": prompt_id, "PMCID": pmcid, "Outcome": "mortality", "Intervention": "Treatment", "Comparator": "placebo"})
                for user, code in (("A", "-1"), ("B", "-1"), ("C", "1")):
                    annotations.append({"UserID": user, "PromptID": prompt_id, "PMCID": pmcid, "Valid Label": "True", "Valid Reasoning": "True", "Label": "decreased" if code == "-1" else "increased", "Annotations": evidence, "Label Code": code, "In Abstract": "False", "Evidence Start": start, "Evidence End": end})
            annotations.append({**annotations[0], "UserID": "invalid", "Valid Label": "False", "Label Code": "1"})

            def csv_bytes(fields: list[str], rows: list[dict[str, str]]) -> bytes:
                handle = io.StringIO(); writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
                return handle.getvalue().encode()

            with tarfile.open(archive, "w:gz") as tf:
                payloads: dict[str, bytes] = {
                    "evidence-inference-2.0/annotations/annotations_merged.csv": csv_bytes(annotation_fields, annotations),
                    "evidence-inference-2.0/annotations/prompts_merged.csv": csv_bytes(prompt_fields, prompts),
                }
                for split, ids in split_ids.items():
                    payloads[f"evidence-inference-2.0/annotations/splits/{split}_article_ids.txt"] = ("\n".join(ids) + "\n").encode()
                for pmcid, text in documents.items():
                    payloads[f"evidence-inference-2.0/annotations/txt_files/PMC{pmcid}.txt"] = text.encode()
                for name, raw in payloads.items():
                    info = tarfile.TarInfo(name); info.size = len(raw); tf.addfile(info, io.BytesIO(raw))

            manifest = build_evidence_inference_corpus(archive, root / "out", minimum_rows=1)
            train = [json.loads(line) for line in (root / "out/train.jsonl").read_text().splitlines()]
            self.assertEqual(len(train), 2)
            self.assertEqual(train[0]["target_action"]["type"], "effect_decreased")
            self.assertEqual(train[0]["input_state"]["evidence_span"], "Treatment reduced mortality compared with placebo.")
            self.assertTrue(train[0]["source_span_verified"])
            self.assertEqual(manifest["family_overlaps"]["train__test"], [])
            self.assertEqual(manifest["discarded"]["invalid_annotation_rows"], 1)


if __name__ == "__main__":
    unittest.main()
