from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

from run_document_vlm_pilot import build_vlm_receipt, parse_and_verify_payload


class DocumentVLMPilotTests(unittest.TestCase):
    def test_exact_native_text_anchor_and_bounded_box_are_verified(self) -> None:
        raw = """```json
        {"document_type_candidate":"research_article","page_role_candidate":"title_page",
         "title_or_heading_candidate":"A randomized trial", "visible_text_anchors":["A randomized trial"],
         "visual_regions":[{"region_type":"heading","bbox_normalized":[0.1,0.1,0.9,0.2]}],
         "uncertainties":[],"abstain":false,"abstention_reason":null}
        ```"""
        payload, report = parse_and_verify_payload(raw, "A randomized trial\nAuthors", page_number=1)
        self.assertEqual(payload["page_role_candidate"], "title_page")
        self.assertTrue(report["passed"])
        self.assertEqual(report["exact_anchor_count"], 1)
        self.assertTrue(report["format_fence_removed"])

    def test_paraphrased_anchor_fails_external_source_verifier(self) -> None:
        raw = """{"document_type_candidate":"research_article","page_role_candidate":"methods",
        "title_or_heading_candidate":null,"visible_text_anchors":["Participants were randomized"],
        "visual_regions":[],"uncertainties":[],"abstain":false,"abstention_reason":null}"""
        _, report = parse_and_verify_payload(raw, "We randomly allocated participants.", page_number=2)
        self.assertFalse(report["passed"])
        self.assertEqual(report["reason_codes"], ["visible_text_anchor_not_exact"])

    def test_out_of_bounds_region_is_rejected(self) -> None:
        raw = """{"document_type_candidate":"other","page_role_candidate":"results",
        "title_or_heading_candidate":null,"visible_text_anchors":["Results"],
        "visual_regions":[{"region_type":"table","bbox_normalized":[0.2,0.2,1.2,0.9]}],
        "uncertainties":[],"abstain":false,"abstention_reason":null}"""
        with self.assertRaisesRegex(ValueError, "bbox_normalized"):
            parse_and_verify_payload(raw, "Results", page_number=3)

    def test_schema_error_reports_key_shape_without_response_content(self) -> None:
        with self.assertRaisesRegex(ValueError, r"missing=.*visible_text_anchors.*unknown=.*summary"):
            parse_and_verify_payload('{"summary":"secret page content"}', "", page_number=1)

    def test_reasoning_prefix_is_removed_before_strict_object_validation(self) -> None:
        raw = """<think>visual reasoning omitted</think>
        {"document_type_candidate":"other","page_role_candidate":"title_page",
        "title_or_heading_candidate":"Results","visible_text_anchors":["Results"],
        "visual_regions":[],"uncertainties":[],"abstain":false,"abstention_reason":null}"""
        _, report = parse_and_verify_payload(raw, "Results", page_number=1)
        self.assertTrue(report["passed"])
        self.assertTrue(report["format_prefix_removed"])

    def test_single_embedded_object_is_extracted_but_two_objects_are_rejected(self) -> None:
        body = """{"document_type_candidate":"other","page_role_candidate":"title_page",
        "title_or_heading_candidate":"Results","visible_text_anchors":["Results"],
        "visual_regions":[],"uncertainties":[],"abstain":false,"abstention_reason":null}"""
        _, report = parse_and_verify_payload("Here is the JSON:\n" + body + "\nDone.", "Results", page_number=1)
        self.assertTrue(report["passed"])
        self.assertTrue(report["format_wrapper_removed"])
        with self.assertRaisesRegex(ValueError, "multiple JSON objects"):
            parse_and_verify_payload(body + "\n" + body, "Results", page_number=1)

    def test_receipt_binds_inputs_model_metrics_and_payload_hash(self) -> None:
        payload = {"abstain": True, "abstention_reason": "page unreadable"}
        receipt = build_vlm_receipt(
            model_id="Qwen/Qwen3-VL-8B-Instruct", revision="60595ebc30ec8e3b1d3b9e65d4943ca011c0006a",
            pdf_sha256="1" * 64, page_image_sha256="2" * 64, prompt_sha256="3" * 64,
            page_number=1, dpi=144, payload=payload, verifier_report={"passed": False},
            elapsed_seconds=2.5, peak_gpu_memory_bytes=1234, input_tokens=100, output_tokens=20,
            torch_version="2.13.0", transformers_version="5.15.0",
        )
        self.assertEqual(receipt["execution_state"], "completed_abstained")
        self.assertEqual(receipt["model"]["revision"], "60595ebc30ec8e3b1d3b9e65d4943ca011c0006a")
        self.assertEqual(receipt["metrics"]["peak_gpu_memory_bytes"], 1234)
        expected = hashlib.sha256(b'{"abstain":true,"abstention_reason":"page unreadable"}').hexdigest()
        self.assertEqual(receipt["payload_sha256"], expected)


if __name__ == "__main__":
    unittest.main()
