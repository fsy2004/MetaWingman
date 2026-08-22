"""Retrieve lawful full text and construct verified report-study-result-estimand lineage."""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError, MeteredModelProvider
from .network_security import public_https_opener, validate_public_https_url
from .provider_factory import build_provider
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


ProviderBuilder = Callable[[dict[str, Any]], Any]
FulltextResolver = Callable[[dict[str, Any], Path], tuple[str | None, dict[str, Any]]]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "entity"


def _bound(root: Path, binding: dict[str, Any], label: str) -> Path:
    raw = Path(str(binding.get("path") or ""))
    path = raw.resolve(strict=False) if raw.is_absolute() else (root / raw).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file() or _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} is missing or has hash drift")
    return path


def _load_previous(request: dict[str, Any], root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(manifest_path) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("selection output manifest hash drift")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = manifest["stage_output"]
        rows = [item for item in output["artifacts"] if item["artifact_id"] == output["state_artifact_id"]]
        if len(rows) != 1:
            raise KeyError("selection state")
        state_path = Path(rows[0]["path"]).resolve(strict=True)
        if _sha(state_path) != rows[0]["sha256"]:
            raise JointLifecycleRunError("selection state artifact hash drift")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_document(state, "joint_selection_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid selection state: {exc}") from exc
    return state, state_path


def _default_fulltext_resolver(record: dict[str, Any], output_dir: Path) -> tuple[str | None, dict[str, Any]]:
    pmcid = str(record.get("pmcid") or "").strip().upper()
    if not pmcid:
        return None, {"record_id": record["record_id"], "status": "unresolved_no_pmcid"}
    if not pmcid.startswith("PMC"):
        pmcid = "PMC" + pmcid
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    validate_public_https_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "MetaWingman/1.0"})
    try:
        with public_https_opener().open(request, timeout=90) as response:
            validate_public_https_url(response.geturl())
            body = response.read(100 * 1024 * 1024 + 1)
    except OSError as exc:
        return None, {"record_id": record["record_id"], "status": "unresolved_network", "error": str(exc)}
    if len(body) > 100 * 1024 * 1024:
        raise JointLifecycleRunError("full text exceeds the frozen 100 MiB byte ceiling")
    raw_path = output_dir / "fulltext" / f"{_id(record['record_id'])}.xml"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists() and raw_path.read_bytes() != body:
        raise JointLifecycleRunError("refusing to overwrite a changed full-text artifact")
    if not raw_path.exists():
        raw_path.write_bytes(body)
    try:
        root = ET.fromstring(body)
        text = "\n".join(part.strip() for part in root.itertext() if part.strip())
    except ET.ParseError as exc:
        return None, {"record_id": record["record_id"], "status": "unresolved_invalid_xml", "error": str(exc)}
    return text or None, {
        "record_id": record["record_id"], "status": "resolved" if text else "unresolved_empty",
        "source_url": url, "artifact_path": str(raw_path), "artifact_sha256": _sha(raw_path),
        "access_route": "public_europe_pmc_fulltext_xml",
    }


def _parse(content: str, criterion_ids: set[str], full_text: str) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JointLifecycleRunError("lineage provider returned invalid JSON") from exc
    required = {"eligibility", "report", "study", "result", "estimand", "extractions"}
    if not isinstance(value, dict) or set(value) != required:
        raise JointLifecycleRunError("lineage provider output has an invalid top-level shape")
    eligibility = value["eligibility"]
    if not isinstance(eligibility, dict) or set(eligibility) != {"decision", "criterion_assessments"}:
        raise JointLifecycleRunError("full-text eligibility output is invalid")
    if eligibility["decision"] not in {"include", "exclude", "abstain"} or not isinstance(eligibility["criterion_assessments"], list):
        raise JointLifecycleRunError("full-text eligibility decision is invalid")
    assessments: dict[str, dict[str, Any]] = {}
    assessment_fields = {"criterion_id", "status", "evidence_quote", "rationale"}
    for row in eligibility["criterion_assessments"]:
        if not isinstance(row, dict) or set(row) != assessment_fields:
            raise JointLifecycleRunError("full-text criterion assessment shape is invalid")
        criterion_id = row["criterion_id"]
        if criterion_id not in criterion_ids or criterion_id in assessments:
            raise JointLifecycleRunError("full-text assessment has unknown or duplicate criterion_id")
        if row["status"] not in {"pass", "fail", "unclear"}:
            raise JointLifecycleRunError("full-text criterion status is invalid")
        if not isinstance(row["evidence_quote"], str) or not isinstance(row["rationale"], str) or not row["rationale"].strip():
            raise JointLifecycleRunError("full-text criterion evidence and rationale are invalid")
        quote = row["evidence_quote"].strip()
        if row["status"] in {"pass", "fail"} and (not quote or quote.casefold() not in full_text.casefold()):
            raise JointLifecycleRunError("full-text pass/fail requires an exact source quote")
        assessments[criterion_id] = row
    if set(assessments) != criterion_ids:
        raise JointLifecycleRunError("full-text output did not assess every frozen criterion")
    expected_decision = (
        "exclude" if any(row["status"] == "fail" for row in assessments.values())
        else "include" if all(row["status"] == "pass" for row in assessments.values())
        else "abstain"
    )
    if eligibility["decision"] != expected_decision:
        raise JointLifecycleRunError("full-text decision conflicts with criterion assessments")
    if not isinstance(value["extractions"], list):
        raise JointLifecycleRunError("lineage extractions must be an array")
    if expected_decision != "include":
        if any(value[key] is not None for key in ("report", "study", "result", "estimand")) or value["extractions"]:
            raise JointLifecycleRunError("excluded or abstained reports cannot emit lineage or extractions")
        return value
    if not all(isinstance(value[key], dict) for key in ("report", "study", "result", "estimand")):
        raise JointLifecycleRunError("included lineage entities must be objects")
    for key in ("report_id",):
        if set(value["report"]) != {key} or not isinstance(value["report"][key], str):
            raise JointLifecycleRunError("report entity is invalid")
    if set(value["study"]) != {"study_id"} or not isinstance(value["study"]["study_id"], str):
        raise JointLifecycleRunError("study entity is invalid")
    if set(value["result"]) != {"result_id"} or not isinstance(value["result"]["result_id"], str):
        raise JointLifecycleRunError("result entity is invalid")
    estimand_fields = {"estimand_id", "population", "contrast", "outcome", "time_window", "effect_measure"}
    if set(value["estimand"]) != estimand_fields or not all(isinstance(value["estimand"][x], str) and value["estimand"][x].strip() for x in estimand_fields):
        raise JointLifecycleRunError("estimand entity is invalid")
    extraction_fields = {"field", "raw", "normalized", "data_type", "unit", "evidence_quote", "confidence"}
    for row in value["extractions"]:
        if not isinstance(row, dict) or set(row) != extraction_fields:
            raise JointLifecycleRunError("extraction output shape is invalid")
        if row["data_type"] not in {"string", "number", "integer", "boolean", "date", "code", "array", "object", "null"}:
            raise JointLifecycleRunError("extraction data_type is invalid")
        if not isinstance(row["evidence_quote"], str) or not row["evidence_quote"].strip():
            raise JointLifecycleRunError("every extraction requires a source quote")
        if isinstance(row["confidence"], bool) or not isinstance(row["confidence"], (int, float)) or not 0 <= row["confidence"] <= 1:
            raise JointLifecycleRunError("extraction confidence is invalid")
    return value


def _edge(edge_id: str, from_type: str, from_id: str, to_type: str, to_id: str, relation: str, anchor_id: str, timestamp: str) -> dict[str, Any]:
    value = {
        "schema_version": "1.0", "edge_id": edge_id,
        "from_node": {"type": from_type, "id": from_id}, "to_node": {"type": to_type, "id": to_id},
        "relationship": relation, "evidence_refs": [anchor_id], "status": "accepted",
        "created_by": {"type": "tool", "id": "exact-span-lineage-verifier", "version": "1.0"},
        "verification": {"status": "passed", "verified_by": "exact-span-lineage-verifier-v1", "verified_at_utc": timestamp, "notes": "Entity chain and exact source span were verified deterministically."},
        "created_at_utc": timestamp,
    }
    validate_document(value, "lineage_edge")
    return value


def report_study_result_lineage_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *,
    provider_builder: ProviderBuilder = build_provider,
    fulltext_resolver: FulltextResolver = _default_fulltext_resolver,
) -> dict[str, Any]:
    if request.get("stage_id") != "data_lineage" or request.get("ordinal") != 4:
        raise JointLifecycleRunError("lineage adapter can execute only canonical stage four")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("lineage adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_lineage_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    selection, selection_path = _load_previous(request, root)
    search_path = _bound(root, selection["search_state_artifact"], "search state")
    protocol_path = _bound(root, selection["protocol_artifact"], "protocol")
    criteria_path = _bound(root, selection["criteria_artifact"], "frozen protocol criteria")
    search_state = json.loads(search_path.read_text(encoding="utf-8"))
    try:
        criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
        validate_document(criteria, "protocol_criteria")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid frozen protocol criteria: {exc}") from exc
    criterion_ids = {item["criterion_id"] for item in criteria["criteria"]}
    records_by_id = {item["record_id"]: item for item in search_state["records"]}
    review_ids = list(dict.fromkeys(selection["include_record_ids"] + selection["abstain_record_ids"]))
    provider_config_path = _bound(root, config["provider_config"], "lineage provider config")
    provider = MeteredModelProvider(
        provider_builder(json.loads(provider_config_path.read_text(encoding="utf-8"))), meter,
        max_input_tokens_per_call=config["maximum_input_tokens_per_call"],
    )
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    documents: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    studies: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    estimands: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    full_text_assessments: list[dict[str, Any]] = []
    full_text_includes: list[str] = []
    full_text_excludes: list[str] = []
    full_text_abstains: list[str] = []
    exclusion_citations: list[dict[str, Any]] = []
    unresolved: list[str] = []
    provenance: list[dict[str, Any]] = []
    for record_id in review_ids:
        record = records_by_id.get(record_id)
        if record is None:
            raise JointLifecycleRunError("selection references an unknown search record")
        text, retrieval = fulltext_resolver(record, output_dir)
        documents.append(retrieval)
        if not text:
            unresolved.append(record_id)
            full_text_abstains.append(record_id)
            full_text_assessments.append({
                "record_id": record_id, "decision": "abstain", "criterion_assessments": [],
                "reason": retrieval.get("status", "full_text_unresolved"),
            })
            continue
        bounded_text = text[: config["maximum_fulltext_characters"]]
        text_path = output_dir / "fulltext" / f"{_id(record_id)}.txt"
        text_path.parent.mkdir(parents=True, exist_ok=True)
        encoded_text = bounded_text.encode("utf-8")
        if text_path.exists() and text_path.read_bytes() != encoded_text:
            raise JointLifecycleRunError("refusing to overwrite a changed normalized full text")
        if not text_path.exists():
            text_path.write_bytes(encoded_text)
        retrieval["normalized_text_artifact"] = {
            "path": str(text_path), "sha256": _sha(text_path),
            "truncated": len(text) > len(bounded_text),
        }
        result = provider.chat([{
            "role": "user", "content": json.dumps({
                "task": "Assess full-text eligibility, then map only eligible reports to study, result, estimand, and source-bound result primitives.",
                "record_id": record_id, "full_text": bounded_text,
                "frozen_criteria": [{
                    "criterion_id": item["criterion_id"], "domain": item["domain"],
                    "label": item["label"], "predicate": item["predicate"],
                    "missing_policy": item["missing_policy"],
                } for item in criteria["criteria"]],
                "rules": [
                    "Use only this full text and assess every frozen criterion exactly once.",
                    "Every pass or fail and every extraction must include an exact verbatim source quote.",
                    "Exclude if any criterion fails; include only if all pass; otherwise abstain.",
                    "For exclude or abstain, report/study/result/estimand must be null and extractions empty.",
                    "Do not infer missing numeric values or use a published review answer.",
                ],
                "required_output": {
                    "eligibility": {
                        "decision": "include|exclude|abstain",
                        "criterion_assessments": [{
                            "criterion_id": "supplied criterion ID", "status": "pass|fail|unclear",
                            "evidence_quote": "exact full-text quote or empty for unclear", "rationale": "text",
                        }],
                    },
                    "report": {"report_id": "stable ID"}, "study": {"study_id": "stable ID"},
                    "result": {"result_id": "stable ID"},
                    "estimand": {
                        "estimand_id": "stable ID", "population": "text", "contrast": "text",
                        "outcome": "text", "time_window": "text", "effect_measure": "text",
                    },
                    "extractions": [{
                        "field": "result primitive", "raw": "source value", "normalized": "typed value",
                        "data_type": "string|number|integer|boolean|date|code|array|object|null",
                        "unit": "unit or null", "evidence_quote": "exact full-text quote", "confidence": "0..1",
                    }],
                },
            }, ensure_ascii=False, sort_keys=True),
        }], model="deepseek-v4-flash", thinking=config["thinking"],
            max_tokens=config["maximum_output_tokens_per_call"], json_output=True)
        if result.model != "deepseek-v4-flash":
            raise JointLifecycleRunError("lineage stage must use deepseek-v4-flash")
        try:
            parsed = _parse(result.content, criterion_ids, bounded_text)
        except JointLifecycleRunError:
            unresolved.append(record_id)
            full_text_abstains.append(record_id)
            full_text_assessments.append({
                "record_id": record_id, "decision": "abstain", "criterion_assessments": [],
                "reason": "invalid_provider_output",
            })
            provenance.append({"record_id": record_id, "model": result.model, "status": "schema_abstention", "response_sha256": result.content_sha256})
            continue
        eligibility = parsed["eligibility"]
        full_text_assessments.append({
            "record_id": record_id, "decision": eligibility["decision"],
            "criterion_assessments": eligibility["criterion_assessments"],
        })
        if eligibility["decision"] == "exclude":
            full_text_excludes.append(record_id)
            for row in eligibility["criterion_assessments"]:
                if row["status"] == "fail":
                    exclusion_citations.append({
                        "record_id": record_id, "title": str(record.get("title") or ""),
                        "criterion_id": row["criterion_id"], "evidence_quote": row["evidence_quote"].strip(),
                        "rationale": row["rationale"].strip(),
                    })
            provenance.append({"record_id": record_id, "model": result.model, "status": "full_text_excluded", "response_sha256": result.content_sha256})
            continue
        if eligibility["decision"] == "abstain":
            full_text_abstains.append(record_id)
            unresolved.append(record_id)
            provenance.append({"record_id": record_id, "model": result.model, "status": "full_text_abstained", "response_sha256": result.content_sha256})
            continue
        full_text_includes.append(record_id)
        verified_rows = []
        for index, row in enumerate(parsed["extractions"], start=1):
            quote = row["evidence_quote"].strip()
            raw_text = str(row["raw"]).strip()
            if quote.casefold() not in bounded_text.casefold() or (raw_text and raw_text.casefold() not in quote.casefold()):
                continue
            anchor_id = _id(f"anchor-{record_id}-{index}")
            start = bounded_text.casefold().find(quote.casefold())
            anchors.append({
                "anchor_id": anchor_id, "record_id": record_id, "quote": quote,
                "character_start": start, "character_end": start + len(quote),
                "verification_status": "passed",
            })
            candidate_id = _id(f"candidate-{record_id}-{index}")
            candidate = {
                "schema_version": "1.0", "candidate_id": candidate_id,
                "document_id": _id(f"document-{record_id}"), "report_id": _id(parsed["report"]["report_id"]),
                "study_id": _id(parsed["study"]["study_id"]), "result_id": _id(parsed["result"]["result_id"]),
                "field": row["field"], "value": {"raw": row["raw"], "normalized": row["normalized"], "data_type": row["data_type"]},
                "unit": row["unit"], "anchor_ids": [anchor_id], "channel": "native_text",
                "created_by": {"type": "model", "id": "deepseek-v4-flash", "version": "frozen"},
                "confidence": row["confidence"],
                "derivation": {"method": "direct", "formula_or_rule": "direct exact-span extraction", "input_candidate_ids": [], "tool": "joint-lineage-adapter", "tool_version": "1.0"},
                "status": "accepted", "verification": {
                    "method": "source_recheck", "status": "passed", "verified_by": "exact-span-value-verifier-v1",
                    "independently_derived": False, "verified_at_utc": request["created_at_utc"], "discrepancy": "",
                }, "created_at_utc": request["created_at_utc"],
            }
            validate_document(candidate, "extraction_candidate")
            candidates.append(candidate)
            verified_rows.append((candidate, anchor_id))
        if not verified_rows:
            unresolved.append(record_id)
            full_text_includes.remove(record_id)
            full_text_abstains.append(record_id)
            full_text_assessments[-1]["decision"] = "abstain"
            full_text_assessments[-1]["reason"] = "no_verified_extraction"
            provenance.append({"record_id": record_id, "model": result.model, "status": "no_verified_extraction", "response_sha256": result.content_sha256})
            continue
        report_id = _id(parsed["report"]["report_id"])
        study_id = _id(parsed["study"]["study_id"])
        result_id = _id(parsed["result"]["result_id"])
        estimand_id = _id(parsed["estimand"]["estimand_id"])
        primary_anchor = verified_rows[0][1]
        reports.append({"report_id": report_id, "record_id": record_id})
        studies.append({"study_id": study_id})
        results.append({"result_id": result_id, "study_id": study_id, "estimand_id": estimand_id})
        estimands.append(dict(parsed["estimand"]) | {"estimand_id": estimand_id})
        edges.extend([
            _edge(_id(f"edge-{report_id}-{study_id}"), "report", report_id, "study", study_id, "is_report_of", primary_anchor, request["created_at_utc"]),
            _edge(_id(f"edge-{study_id}-{result_id}"), "study", study_id, "result", result_id, "reports_result", primary_anchor, request["created_at_utc"]),
        ])
        provenance.append({
            "record_id": record_id, "model": result.model, "status": "verified",
            "response_sha256": result.content_sha256, "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        })
    accounted = set(full_text_includes) | set(full_text_excludes) | set(full_text_abstains)
    if (
        accounted != set(review_ids)
        or set(full_text_includes) & set(full_text_excludes)
        or set(full_text_includes) & set(full_text_abstains)
        or set(full_text_excludes) & set(full_text_abstains)
    ):
        raise JointLifecycleRunError("full-text eligibility did not account for every carried-forward record exactly once")
    complete = len(results)
    state = {
        "schema_version": "1.0", "stage_id": "data_lineage", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "selection_state_artifact": {"path": str(selection_path), "sha256": _sha(selection_path)},
        "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
        "documents": documents, "anchors": anchors, "reports": reports, "studies": studies,
        "results": results, "estimands": estimands, "extraction_candidates": candidates,
        "lineage_edges": edges, "full_text_assessments": full_text_assessments,
        "full_text_include_record_ids": full_text_includes,
        "full_text_exclude_record_ids": full_text_excludes,
        "full_text_abstain_record_ids": full_text_abstains,
        "full_text_exclusion_citations": exclusion_citations,
        "all_full_text_records_accounted_for": True,
        "unresolved_record_ids": list(dict.fromkeys(unresolved)),
        "complete_verified_lineage_count": complete, "model_provenance": provenance,
        "published_reference_accessed": False,
    }
    state_path = output_dir / "lineage-state.json"
    atomic_write_json(state_path, state, "joint_lineage_stage_state")
    artifacts = [{
        "artifact_id": "lineage_state", "path": str(state_path), "sha256": _sha(state_path),
        "media_type": "application/json", "role": "stage_state",
    }]
    status = "completed" if complete else "abstained"
    output = {
        "schema_version": "1.0", "stage_id": "data_lineage", "status": status,
        "state_artifact_id": "lineage_state", "artifacts": artifacts,
        "scientific_checks": [{
            "check_id": "report_study_result_estimand_lineage",
            "status": "passed" if complete else "abstained", "evidence_artifact_ids": ["lineage_state"],
        }], "terminal_reason": None if complete else "no record produced verified full-text result lineage",
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
