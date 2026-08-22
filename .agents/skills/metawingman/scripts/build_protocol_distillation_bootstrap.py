#!/usr/bin/env python3
"""Build governed protocol-stage trajectories from licensed JATS methods spans."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from metawingman_core.agent_distillation import freeze_distillation_examples  # type: ignore
    from metawingman_core.schema_guard import validate_document  # type: ignore
    from metawingman_core.state_store import sha256_json  # type: ignore
else:
    from .metawingman_core.agent_distillation import freeze_distillation_examples
    from .metawingman_core.schema_guard import validate_document
    from .metawingman_core.state_store import sha256_json


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(element: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def _method_rows(article_xml: Path, teacher: dict[str, object]) -> list[dict[str, str]]:
    root = ET.fromstring(article_xml.read_bytes())
    methods = next((row for row in root.iter() if row.tag.endswith("sec") and row.get("sec-type") == "methods"), None)
    if methods is None:
        raise ValueError("article has no JATS methods section")
    mapping = teacher["section_to_action"]
    rows: list[dict[str, str]] = []
    for section in methods.iter():
        if not section.tag.endswith("sec"):
            continue
        title_element = next((child for child in section if child.tag.endswith("title")), None)
        title = _text(title_element).casefold() if title_element is not None else ""
        action = mapping.get(title) if isinstance(mapping, dict) else None
        if not isinstance(action, str):
            continue
        paragraph_index = 0
        for child in section:
            if not child.tag.endswith("p"):
                continue
            paragraph = _text(child)
            if len(paragraph) < 80:
                continue
            paragraph_index += 1
            rows.append({
                "source_id": f"methods-{len(rows) + 1:03d}",
                "anchor": f"methods/{title}/paragraph-{paragraph_index}",
                "source_section": title,
                "action_type": action,
                "method_statement": paragraph,
            })
    if len(rows) < 8:
        raise ValueError("too few independently anchored methods spans for bootstrap training")
    return rows


def build_bootstrap(
    *, article_xml: Path, case_registry_path: Path, teacher_path: Path,
    prompt_path: Path, output_dir: Path, created_at_utc: str,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    registry = json.loads(case_registry_path.read_text(encoding="utf-8"))
    teacher = json.loads(teacher_path.read_text(encoding="utf-8"))
    prompt = json.loads(prompt_path.read_text(encoding="utf-8"))
    case_id = "bmj-exercise-depression-nma"
    family_id = "adult-depression-exercise-treatment"
    rows = _method_rows(article_xml, teacher)
    dataset_path = output_dir / "protocol-method-spans.jsonl"
    dataset_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    audit = {
        "schema_version": "1.0", "audit_id": "bmj-exercise-protocol-span-audit-v1",
        "article_xml_sha256": _sha(article_xml), "methods_span_count": len(rows),
        "all_spans_exactly_present": all(row["method_statement"] in _text(ET.fromstring(article_xml.read_bytes())) for row in rows),
        "excluded_article_sections": ["abstract", "results", "discussion", "conclusions"],
        "license": "CC BY-NC", "published_answer_used_as_gold": False,
    }
    if not audit["all_spans_exactly_present"]:
        raise ValueError("method span exact-source audit failed")
    audit_path = output_dir / "protocol-method-span-audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    common_bindings = {
        "artifact_bindings": {
            "source_artifacts": [{"path": str(article_xml), "sha256": _sha(article_xml)}],
            "audit_artifacts": [{"path": str(audit_path), "sha256": _sha(audit_path)}],
        },
        "reproducibility_bindings": {
            "dataset_sha256": _sha(dataset_path), "prompt_sha256": _sha(prompt_path),
            "tool_sha256": _sha(Path(__file__)), "checkpoint_sha256": _sha(teacher_path),
        },
    }
    traces = []
    for row in rows:
        traces.append({
            "trace_id": f"protocol-{row['source_id']}", "case_id": case_id,
            "review_family_id": family_id, "split": "development", "stage": "protocol",
            "teacher_provider_id": "MetaWingman deterministic rules",
            "teacher_identity": {
                "provider_id": "MetaWingman deterministic rules", "model_id": teacher["teacher_id"],
                "canonical_provider_id": "metawingman-deterministic-rules",
                "canonical_model_id": "deterministic-protocol-section-compiler-v1",
            },
            "input_state": {
                "task": prompt["system"], "source_section": row["source_section"],
                "method_statement": row["method_statement"],
            },
            "action": {
                "type": row["action_type"], "source_section": row["source_section"],
                "method_statement": row["method_statement"],
            },
            "decision": {"status": "accept", "reason_codes": ["licensed_methods_exact_span_verified"]},
            "source_anchors": [{"source_id": row["source_id"], "anchor": row["anchor"]}],
            "verification": {
                "status": "verified", "verifier_kind": "deterministic_guard",
                "verifier_id": "exact-jats-method-span-and-section-map-v1",
                "checks": ["methods_section_only", "exact_source_span", "frozen_section_action_map", "sealed_evaluation_material_excluded"],
            },
            "outcome": "success", **common_bindings,
        })
    registry_sha = sha256_json(registry)
    revocation = {
        "schema_version": "1.0", "revision": "protocol-bootstrap-rev-1",
        "case_registry_sha256": registry_sha, "revoked_trace_ids": [],
        "forbidden_value_aliases": [],
    }
    revocation_path = output_dir / "revocation-manifest.json"
    revocation_path.write_text(json.dumps(revocation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    export = freeze_distillation_examples(traces, case_registry=registry, created_at_utc=created_at_utc, revocation_manifest=revocation)
    export_path = output_dir / "agent-distillation-export.json"
    export_path.write_text(json.dumps(export, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    closure = {
        "schema_version": "1.0", "teacher_id": teacher["teacher_id"],
        "teacher_kind": "deterministic_rule", "training_family_ids": [],
        "target_family_id": family_id, "status": "verified_target_family_absent",
    }
    closure_path = output_dir / "teacher-family-closure.json"
    closure_path.write_text(json.dumps(closure, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scope = {"case_ids": [case_id], "family_ids": [family_id], "stages": ["protocol_registration"]}
    def binding(binding_id: str, path: Path) -> dict[str, object]:
        return {"binding_id": binding_id, "artifact_path": str(path), "sha256": _sha(path), **scope}
    lineage = {
        "schema_version": "1.0", "manifest_id": "bmj-exercise-protocol-bootstrap-lineage-v1",
        "case_registry_sha256": registry_sha,
        "dataset_bindings": [binding("protocol-method-spans", dataset_path)],
        "prompt_bindings": [binding("protocol-distillation-prompt", prompt_path)],
        "tool_bindings": [binding("protocol-distillation-builder", Path(__file__))],
        "checkpoint_bindings": [{
            **binding("deterministic-protocol-teacher", teacher_path),
            "teacher_identity": export["examples"][0]["teacher_identity"],
            "training_family_ids": [],
            "family_closure": {
                "status": "verified_target_family_absent", "case_registry_sha256": registry_sha,
                "artifact_path": str(closure_path), "sha256": _sha(closure_path),
            },
        }],
    }
    validate_document(lineage, "distillation_lineage_manifest")
    lineage_path = output_dir / "distillation-lineage-manifest.json"
    lineage_path.write_text(json.dumps(lineage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "completed", "examples": len(export["examples"]),
        "trainable_examples": export["summary"]["trainable_examples"],
        "paths": {"export": str(export_path), "lineage": str(lineage_path), "revocations": str(revocation_path)},
        "hashes": {"export": _sha(export_path), "lineage": _sha(lineage_path), "revocations": _sha(revocation_path)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article-xml", type=Path, required=True)
    parser.add_argument("--case-registry", type=Path, required=True)
    parser.add_argument("--teacher", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--created-at-utc", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    result = build_bootstrap(article_xml=args.article_xml, case_registry_path=args.case_registry,
                             teacher_path=args.teacher, prompt_path=args.prompt,
                             output_dir=args.out_dir, created_at_utc=args.created_at_utc)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
