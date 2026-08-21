#!/usr/bin/env python3
"""Run a hash-bound GLM-4.6V scientific-document page pilot."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


MODEL_DEFAULT = "glm-4.6v"
ENDPOINT_DEFAULT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
PROMPT = """Inspect this scientific-document page as a visual extraction candidate. Return one JSON object only with exactly these fields: document_type_candidate (research_article, supplement, or other), page_role_candidate (short string), title_or_heading_candidate (string or null), visible_text_anchors (1-5 short verbatim excerpts visibly present on the page, or an empty array only when abstaining), visual_regions (array of objects with region_type from heading, body, table, figure, other and bbox_normalized [x0,y0,x1,y1] in 0..1), uncertainties (array of strings), abstain (boolean), abstention_reason (string or null). Do not infer study results, methods, or identities that are not visibly present. Use exact excerpts, not paraphrases."""
EXPECTED_KEYS = {
    "document_type_candidate", "page_role_candidate", "title_or_heading_candidate",
    "visible_text_anchors", "visual_regions", "uncertainties", "abstain", "abstention_reason",
}
REGION_TYPES = {"heading", "body", "table", "figure", "other"}
DOCUMENT_TYPES = {"research_article", "supplement", "other"}


def _canonical(document: Any) -> bytes:
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_and_verify_payload(raw_output: str, native_text: str, *, page_number: int) -> tuple[dict[str, Any], dict[str, Any]]:
    del page_number
    text = raw_output.strip()
    fence_removed = False
    prefix_removed = False
    wrapper_removed = False
    think = re.fullmatch(r"<think>.*?</think>\s*(.*)", text, flags=re.DOTALL | re.IGNORECASE)
    if think:
        text = think.group(1).strip()
        prefix_removed = True
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
        fence_removed = True
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.find("{")
        if start < 0:
            raise ValueError("VLM output is not one JSON object") from exc
        try:
            payload, consumed = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as nested:
            raise ValueError("VLM output is not one JSON object") from nested
        suffix = text[start + consumed:]
        if "{" in suffix or "}" in suffix:
            raise ValueError("VLM output contains multiple JSON objects")
        wrapper_removed = bool(text[:start].strip() or suffix.strip())
    if not isinstance(payload, dict):
        raise ValueError("VLM payload is not an object")
    if set(payload) != EXPECTED_KEYS:
        missing = sorted(EXPECTED_KEYS - set(payload))
        unknown = sorted(set(payload) - EXPECTED_KEYS)
        raise ValueError(f"VLM payload key shape mismatch: missing={missing}; unknown={unknown}")
    if payload["document_type_candidate"] not in DOCUMENT_TYPES:
        raise ValueError("document_type_candidate is invalid")
    if not isinstance(payload["page_role_candidate"], str) or not payload["page_role_candidate"].strip():
        raise ValueError("page_role_candidate is invalid")
    if payload["title_or_heading_candidate"] is not None and not isinstance(payload["title_or_heading_candidate"], str):
        raise ValueError("title_or_heading_candidate is invalid")
    anchors = payload["visible_text_anchors"]
    if not isinstance(anchors, list) or len(anchors) > 5 or any(not isinstance(item, str) or not item.strip() for item in anchors):
        raise ValueError("visible_text_anchors is invalid")
    regions = payload["visual_regions"]
    if not isinstance(regions, list):
        raise ValueError("visual_regions is invalid")
    for region in regions:
        if not isinstance(region, dict) or set(region) != {"region_type", "bbox_normalized"} or region["region_type"] not in REGION_TYPES:
            raise ValueError("visual region is invalid")
        box = region["bbox_normalized"]
        if not isinstance(box, list) or len(box) != 4 or any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in box):
            raise ValueError("bbox_normalized is invalid")
        x0, y0, x1, y1 = [float(value) for value in box]
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("bbox_normalized is out of bounds")
    if not isinstance(payload["uncertainties"], list) or any(not isinstance(item, str) for item in payload["uncertainties"]):
        raise ValueError("uncertainties is invalid")
    if not isinstance(payload["abstain"], bool):
        raise ValueError("abstain is invalid")
    if payload["abstention_reason"] is not None and not isinstance(payload["abstention_reason"], str):
        raise ValueError("abstention_reason is invalid")
    if payload["abstain"] and not (payload["abstention_reason"] or "").strip():
        raise ValueError("abstention requires a reason")
    if not payload["abstain"] and not anchors:
        raise ValueError("non-abstained candidate requires a visible text anchor")
    source = _normalize_text(native_text)
    unmatched = [anchor for anchor in anchors if _normalize_text(anchor) not in source]
    reasons = ["visible_text_anchor_not_exact"] if unmatched else []
    report = {
        "passed": not reasons and not payload["abstain"],
        "reason_codes": reasons + (["model_abstained"] if payload["abstain"] else []),
        "exact_anchor_count": len(anchors) - len(unmatched),
        "unmatched_anchor_count": len(unmatched),
        "bounded_region_count": len(regions),
        "format_fence_removed": fence_removed,
        "format_prefix_removed": prefix_removed,
        "format_wrapper_removed": wrapper_removed,
        "verification_policy": "exact_normalized_native_text_and_bounded_regions",
    }
    return payload, report


def build_vlm_receipt(
    *, model_id: str, revision: str, pdf_sha256: str, page_image_sha256: str,
    prompt_sha256: str, page_number: int, dpi: int, payload: dict[str, Any],
    verifier_report: dict[str, Any], elapsed_seconds: float, peak_gpu_memory_bytes: int,
    input_tokens: int | None, output_tokens: int | None, torch_version: str,
    transformers_version: str,
) -> dict[str, Any]:
    state = "completed_abstained" if payload.get("abstain") else (
        "completed_verified_candidate" if verifier_report.get("passed") else "completed_unverified_candidate"
    )
    return {
        "schema_version": "1.0", "execution_state": state,
        "model": {"provider": "Zhipu GLM", "model_id": model_id, "revision": revision},
        "inputs": {"pdf_sha256": pdf_sha256, "page_image_sha256": page_image_sha256, "prompt_sha256": prompt_sha256, "page_number": page_number, "dpi": dpi},
        "payload": payload, "payload_sha256": _sha_bytes(_canonical(payload)),
        "verifier_report": verifier_report,
        "metrics": {"elapsed_seconds": elapsed_seconds, "peak_gpu_memory_bytes": peak_gpu_memory_bytes, "input_tokens": input_tokens, "output_tokens": output_tokens},
        "runtime": {"torch_version": torch_version, "transformers_version": transformers_version},
        "claim_boundary": "visual_extraction_candidate_not_scientific_acceptance",
    }


def _request_glm(image_png: bytes, *, endpoint: str, model: str, api_key: str, max_tokens: int) -> dict[str, Any]:
    data_url = "data:image/png;base64," + base64.b64encode(image_png).decode("ascii")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": PROMPT},
        ]}],
        "stream": False, "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(endpoint, data=_canonical(body), method="POST", headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "MetaWingman/GLM-document-pilot-1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            parsed = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GLM HTTP {exc.code}: request rejected") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"GLM request failed: {type(exc).__name__}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("GLM response is not an object")
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--model", default=MODEL_DEFAULT)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--endpoint", default=ENDPOINT_DEFAULT)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    api_key = os.environ.get("GLM_API_KEY", "").strip()
    if not api_key:
        print(json.dumps({"execution_state": "failed_before_call", "error": "GLM_API_KEY capability missing"}))
        return 2
    try:
        import fitz
        if args.page < 1 or args.dpi < 72 or args.dpi > 300:
            raise ValueError("page or dpi is outside the frozen pilot boundary")
        pdf = fitz.open(args.pdf)
        try:
            if args.page > pdf.page_count:
                raise ValueError("page exceeds PDF page count")
            page = pdf[args.page - 1]
            native_text = page.get_text("text")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(args.dpi / 72, args.dpi / 72), alpha=False)
            image_png = pixmap.tobytes("png")
        finally:
            pdf.close()
        started = time.monotonic()
        response = _request_glm(image_png, endpoint=args.endpoint, model=args.model, api_key=api_key, max_tokens=args.max_tokens)
        elapsed = time.monotonic() - started
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("GLM response has no choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("GLM response content is missing")
        payload, verifier = parse_and_verify_payload(content, native_text, page_number=args.page)
        usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        receipt = build_vlm_receipt(
            model_id=str(response.get("model") or args.model), revision=args.model_revision,
            pdf_sha256=_sha_file(args.pdf), page_image_sha256=_sha_bytes(image_png),
            prompt_sha256=_sha_bytes(PROMPT.encode("utf-8")), page_number=args.page, dpi=args.dpi,
            payload=payload, verifier_report=verifier, elapsed_seconds=elapsed,
            peak_gpu_memory_bytes=0, input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"),
            torch_version="not_used_hosted_api", transformers_version="not_used_hosted_api",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temporary, args.output)
        print(json.dumps({"execution_state": receipt["execution_state"], "output": str(args.output), "elapsed_seconds": elapsed, "payload_sha256": receipt["payload_sha256"]}, indent=2))
        return 0 if receipt["execution_state"] == "completed_verified_candidate" else 3
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"execution_state": "failed", "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
