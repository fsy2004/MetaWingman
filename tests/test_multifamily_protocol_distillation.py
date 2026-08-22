from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from metawingman.scripts.build_multifamily_protocol_corpus import extract_method_examples, select_records
from metawingman.scripts.run_multifamily_protocol_training import DEFAULT_SYSTEM_PROMPT, _balance_action_rows, _encode_supervised, _messages, _score, load_corpus, load_test_corpus
from metawingman.scripts.build_csmed_fulltext_agent_corpus import build_csmed_corpus


XML = b"""<article><body><sec sec-type="methods"><title>Methods</title>
<sec><title>Search strategy</title><p>We searched MEDLINE and Embase from inception using controlled vocabulary and keywords, with no language restriction.</p></sec>
<sec><title>Eligibility criteria</title><p>We included randomized trials enrolling adults and comparing an active intervention with usual care or placebo.</p></sec>
<sec><title>Statistical analysis</title><p>We pooled effect estimates with random effects models and quantified heterogeneity using the I squared statistic.</p></sec>
</sec></body></article>"""


class MultifamilyProtocolCorpusTests(unittest.TestCase):
    def test_action_balancing_is_deterministic_and_equalizes_labels(self) -> None:
        rows = [
            {"example_id": f"exclude-{index}", "target_action": {"type": "exclude"}}
            for index in range(4)
        ] + [{"example_id": "include-0", "target_action": {"type": "include"}}]
        first = _balance_action_rows(rows, seed=17)
        second = _balance_action_rows(rows, seed=17)
        self.assertEqual([row["example_id"] for row in first], [row["example_id"] for row in second])
        counts = {
            label: sum(row["target_action"]["type"] == label for row in first)
            for label in ("include", "exclude")
        }
        self.assertEqual(counts, {"include": 4, "exclude": 4})

    def test_record_selection_is_deterministic_and_family_disjoint(self) -> None:
        records = []
        for split in ("train", "development"):
            for index in range(8):
                records.append({
                    "record_id": f"{split}-{index}", "family_id": f"{split}-family-{index}",
                    "split": split, "pmcid": f"PMC{index + (100 if split == 'train' else 200)}",
                    "declared_license": "cc by", "title": "Systematic review",
                    "biomedical_stratum": {"primary_specialty": "general-medicine"},
                })
        first = select_records(records, max_train_articles=4, max_dev_articles=3)
        second = select_records(list(reversed(records)), max_train_articles=4, max_dev_articles=3)
        self.assertEqual(first, second)
        self.assertEqual({row["family_id"] for row in first["train"]} & {row["family_id"] for row in first["development"]}, set())

    def test_jats_methods_are_exactly_anchored_and_mapped(self) -> None:
        record = {"record_id": "x", "family_id": "family-x", "split": "train", "pmcid": "PMCX", "title": "Review"}
        rows = extract_method_examples(XML, record)
        self.assertEqual({row["target_action"]["type"] for row in rows}, {"search", "eligibility", "synthesis"})
        self.assertTrue(all(row["method_statement"] in XML.decode() for row in rows))
        self.assertTrue(all(row["published_answer_used_as_gold"] is False for row in rows))
        trace = rows[0]["target_method_trace"]
        self.assertIn("decision_tension", trace)
        self.assertIn("disconfirmation_design", trace)
        self.assertIn("evidence_gap_anchor", trace)
        self.assertIn("stopping_rule", trace)

    def test_training_prompt_targets_skill_driven_method_agent_not_plain_classifier(self) -> None:
        prompt = DEFAULT_SYSTEM_PROMPT.casefold()
        self.assertIn("skill-driven", prompt)
        self.assertIn("decision-aware topic", prompt)
        self.assertIn("risk-impact evidence acquisition", prompt)
        row = {
            "input_state": {"source_section": "Search strategy", "method_statement": "Search methods were specified."},
            "target_action": {"type": "search"},
            "target_decision": {"status": "accept"},
            "target_method_trace": {
                "decision_tension": "Search coverage can change the review conclusion.",
                "disconfirmation_design": "Check whether a required source is absent.",
                "evidence_gap_anchor": "Search strategy",
                "stopping_rule": "Stop after exact-span verification.",
            },
        }
        content = _messages(row, True)[-1]["content"]
        self.assertIn("target_method_trace", content)

    def test_training_loader_rejects_family_overlap(self) -> None:
        row = {"example_id": "a", "family_id": "same", "input_state": {}, "target_action": {"type": "search", "source_section": "search"}, "target_decision": {"status": "accept"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("train.jsonl", "development.jsonl"):
                (root / name).write_text(json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "family overlap"):
                load_corpus(root / "train.jsonl", root / "development.jsonl", min_train=1, min_dev=1)

    def test_jsonl_reader_does_not_split_unicode_line_separator_inside_text(self) -> None:
        row = {"example_id": "a", "family_id": "train", "input_state": {"text": "left\u2028right"}, "target_action": {"type": "search"}, "target_decision": {"status": "accept"}}
        other = {**row, "example_id": "b", "family_id": "development"}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "train.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "dev.jsonl").write_text(json.dumps(other, ensure_ascii=False) + "\n", encoding="utf-8")
            train, _ = load_corpus(root / "train.jsonl", root / "dev.jsonl", min_train=1, min_dev=1)
            self.assertEqual(train[0]["input_state"]["text"], "left\u2028right")

    def test_supervised_encoding_keeps_completion_when_prompt_exceeds_context(self) -> None:
        class Tokenizer:
            eos_token_id = 99
            def apply_chat_template(self, messages, **_kwargs):
                return "TARGET" if messages[-1]["role"] == "assistant" else "PROMPT"
            def __call__(self, text, **_kwargs):
                return {"input_ids": list(range(100)) if text == "PROMPT" else list(range(100)) + [901, 902]}

        row = {"input_state": {"candidate_full_text": "long"}, "target_action": {"type": "include"}, "target_decision": {"status": "include"}}
        encoded = _encode_supervised(row, Tokenizer(), "system", max_length=16)
        self.assertEqual(encoded["input_ids"][-2:], [901, 902])
        self.assertEqual(encoded["labels"][-2:], [901, 902])
        self.assertTrue(any(label != -100 for label in encoded["labels"]))

    def test_test_loader_requires_a_third_unseen_family_set(self) -> None:
        def row(example: str, family: str) -> dict:
            return {"example_id": example, "family_id": family, "input_state": {}, "target_action": {"type": "include", "source_section": "full_text_selection"}, "target_decision": {"status": "include"}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in (("train.jsonl", row("a", "train")), ("dev.jsonl", row("b", "dev")), ("test.jsonl", row("c", "test"))):
                (root / name).write_text(json.dumps(value) + "\n", encoding="utf-8")
            train, dev, test = load_test_corpus(root / "train.jsonl", root / "dev.jsonl", root / "test.jsonl", min_train=1, min_dev=1, min_test=1)
            self.assertEqual([len(train), len(dev), len(test)], [1, 1, 1])

    def test_selection_prompt_preserves_criteria_before_candidate_full_text(self) -> None:
        row = {"input_state": {"review_title": "R", "eligibility_criteria": "CRITERIA", "candidate_title": "C", "candidate_abstract": "A", "candidate_full_text": "FULL"}}
        content = _messages(row, False)[1]["content"]
        self.assertLess(content.index("CRITERIA"), content.index("FULL"))

    def test_scoring_uses_the_frozen_training_context_length(self) -> None:
        import torch

        class Tokenizer:
            eos_token_id = 0
            seen_max_length = None

            def apply_chat_template(self, *_args, **_kwargs): return "prompt"
            def __call__(self, _text, **kwargs):
                self.seen_max_length = kwargs["max_length"]
                class Batch(dict):
                    def to(self, _device): return self
                return Batch(input_ids=torch.tensor([[1]]))
            def decode(self, *_args, **_kwargs): return '{"target_action":{"type":"include"},"target_decision":{"status":"include"}}'

        class Model:
            def eval(self): return self
            def generate(self, **_kwargs): return torch.tensor([[1, 2]])

        tokenizer = Tokenizer()
        row = {"example_id": "x", "family_id": "f", "input_state": {}, "target_action": {"type": "include"}, "target_decision": {"status": "include"}}
        _score(Model(), tokenizer, [row], torch.device("cpu"), 1, "system", max_input_length=1536)
        self.assertEqual(tokenizer.seen_max_length, 1536)

    def test_csmed_builder_uses_criteria_but_not_review_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); archive_path = root / "fixture.zip"
            fields = ["review_id", "document_id", "decision", "reason_for_exclusion", "title", "abstract", "main_text"]
            with zipfile.ZipFile(archive_path, "w") as archive:
                for index, split in enumerate(("train", "dev", "test"), 1):
                    review_id = f"R{index}"
                    metadata = {review_id: {"review_id": review_id, "title": "Common disease review", "criteria_text": "Adults with common disease; randomized trials.", "abstract": "SECRET PUBLISHED RESULT"}}
                    csv_text = ",".join(fields) + f"\n{review_id},D1,included,,Candidate,Candidate abstract,Full candidate text\n"
                    archive.writestr(f"CSMeD-FT/CSMeD-FT-{split}.csv", csv_text)
                    archive.writestr(f"CSMeD-FT/CSMeD-FT-{split}_reviews_metadata.json", json.dumps(metadata))
            manifest = build_csmed_corpus(archive_path, root / "out", minimum_rows=1)
            row = json.loads((root / "out/train.jsonl").read_text(encoding="utf-8"))
            self.assertIn("Adults with common disease", row["input_state"]["eligibility_criteria"])
            self.assertNotIn("SECRET PUBLISHED RESULT", json.dumps(row))
            self.assertEqual(manifest["datasets"]["train"]["families"], 1)


if __name__ == "__main__":
    unittest.main()
