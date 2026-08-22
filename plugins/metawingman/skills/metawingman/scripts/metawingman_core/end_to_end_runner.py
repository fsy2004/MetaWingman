"""Bounded AI-only execution and deterministic scoring for reconstruction slots."""

from __future__ import annotations

import json
import re
import time
from typing import Any


FRAMEWORK_FIELDS = (
    "population", "intervention_or_exposure", "comparator", "outcome",
    "study_design", "synthesis_route",
)


def _shape_signature(value: Any) -> Any:
    """Describe JSON structure without retaining semantic values or candidate IDs."""
    if isinstance(value, dict):
        return {str(key): _shape_signature(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        item_shapes = []
        for item in value:
            shape = _shape_signature(item)
            if shape not in item_shapes:
                item_shapes.append(shape)
        return {"type": "array", "length": len(value), "item_shapes": item_shapes}
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def _call_json(provider: Any, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    result = provider.chat(
        [
            {"role": "system", "content": "Return one strict JSON object. Use only supplied evidence and IDs."},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model="deepseek-v4-flash",
        max_tokens=2048,
        json_output=True,
    )
    try:
        parsed = json.loads(result.content)
        if not isinstance(parsed, dict):
            parsed = None
    except (TypeError, json.JSONDecodeError):
        parsed = None
    return parsed, result.audit_record()


def _protocol_contract(value: Any) -> tuple[dict[str, Any] | None, list[str] | None, bool]:
    if not isinstance(value, dict):
        return None, None, False
    framework, framework_normalized = normalize_question_framework(value.get("question_framework"))
    criteria = value.get("eligibility_criteria")
    criteria_normalized = False
    if isinstance(criteria, str) and criteria.strip():
        criteria = [criteria.strip()]
        criteria_normalized = True
    if framework is None or not isinstance(criteria, list) or not criteria or not all(
        isinstance(item, str) and item.strip() for item in criteria
    ):
        return None, None, False
    return framework, [item.strip() for item in criteria], framework_normalized or criteria_normalized


def _synthesis_contract(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("claims"), list)
        and isinstance(value.get("limitations"), list)
        and all(isinstance(item, str) for item in value["limitations"])
    )


def _valid_framework(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != set(FRAMEWORK_FIELDS):
        return False
    return all(
        isinstance(value[field], str) and bool(value[field].strip())
        if field == "synthesis_route"
        else isinstance(value[field], list) and bool(value[field])
        and all(isinstance(item, str) and bool(item.strip()) for item in value[field])
        for field in FRAMEWORK_FIELDS
    )


def normalize_question_framework(value: Any) -> tuple[dict[str, Any] | None, bool]:
    """Normalize schema-equivalent shapes without changing semantic content."""
    if not isinstance(value, dict):
        return None, False
    output: dict[str, Any] = {}
    changed = set(value) != set(FRAMEWORK_FIELDS)
    for field in FRAMEWORK_FIELDS:
        item = value.get(field)
        if field == "synthesis_route":
            if isinstance(item, list) and len(item) == 1 and isinstance(item[0], str):
                item = item[0]
                changed = True
            if not isinstance(item, str) or not item.strip():
                return None, changed
            output[field] = item.strip()
            continue
        if isinstance(item, str) and item.strip():
            item = [item.strip()]
            changed = True
        if not isinstance(item, list) or not item or not all(isinstance(part, str) and part.strip() for part in item):
            return None, changed
        output[field] = [part.strip() for part in item]
    return output, changed


def execute_reconstruction_slot(
    *,
    plan_id: str,
    case: dict[str, Any],
    configuration: dict[str, Any],
    seed: int,
    provider: Any,
    records: list[dict[str, Any]],
    acquisition_output: dict[str, Any],
) -> dict[str, Any]:
    """Execute protocol, screening/extraction, and synthesis without references."""
    started = time.perf_counter()
    record_index = {str(row["id"]): row for row in records}
    ranked = [str(value) for value in acquisition_output.get("retrieval_candidate_ids", [])]
    visible_ids = [value for value in ranked if value in record_index][:100]
    visible_records = [
        {
            "id": value,
            "title": str(record_index[value].get("title", "")),
            "abstract": str(record_index[value].get("abstract", ""))[:1500],
        }
        for value in visible_ids
    ]
    topic_mode = (
        "decision-aware question and method co-design with explicit feasibility and decision-use checks"
        if configuration["topic_opportunity_control"] else
        "generic structured restatement of the supplied review question"
    )
    protocol_raw, protocol_audit = _call_json(provider, {
        "stage": "protocol",
        "mode": topic_mode,
        "operational_question": case["operational_question"],
        "eligibility_criteria": case["eligibility_criteria"],
        "historical_cutoff": case["historical_cutoff_at_utc"],
        "required_output": {
            "question_framework": {
                "population": ["non-empty population phrase"],
                "intervention_or_exposure": ["non-empty intervention or exposure phrase"],
                "comparator": ["non-empty comparator phrase"],
                "outcome": ["one or more outcome phrases"],
                "study_design": ["one or more eligible study-design phrases"],
                "synthesis_route": "one non-empty synthesis-route string",
            },
            "eligibility_criteria": ["non-empty strings"],
        },
        "prohibition": "Do not name or infer a target review, authors, DOI, or published answer.",
    })
    protocol_initial_shape = _shape_signature(protocol_raw)
    framework, criteria, protocol_normalized = _protocol_contract(protocol_raw)
    protocol_repair_audit = None
    protocol_repaired = False
    if framework is None:
        protocol_raw, protocol_repair_audit = _call_json(provider, {
            "stage": "protocol_schema_repair",
            "invalid_output": protocol_raw,
            "invalid_output_shape": protocol_initial_shape,
            "required_output": {
                "question_framework": {field: (
                    "one non-empty synthesis-route string" if field == "synthesis_route"
                    else ["one or more non-empty strings"]
                ) for field in FRAMEWORK_FIELDS},
                "eligibility_criteria": ["one or more non-empty strings"],
            },
            "instruction": "Repair structure only. Preserve supported meaning; do not add evidence or identifiers.",
        })
        framework, criteria, protocol_normalized = _protocol_contract(protocol_raw)
        protocol_repaired = framework is not None
    if framework is None:
        protocol = {"status": "abstained_provider_schema_invalid"}
    else:
        protocol = {
            **protocol_raw,
            "question_framework": framework,
            "eligibility_criteria": criteria,
            "status": (
                "completed_after_schema_repair" if protocol_repaired else
                "completed_deterministic_schema_normalization"
                if protocol_normalized else "completed"
            ),
        }

    proposed: list[str] = []
    extractions: list[dict[str, Any]] = []
    unknown: list[str] = []
    screening_audits: list[dict[str, Any]] = []
    invalid_batches = 0
    batches = [visible_records[index:index + 25] for index in range(0, len(visible_records), 25)]
    for batch_index, batch in enumerate(batches, start=1):
        screening_raw, screening_audit = _call_json(provider, {
            "stage": "screening_and_abstract_extraction",
            "batch_index": batch_index,
            "batch_count": len(batches),
            "protocol_question_framework": framework,
            "eligibility_criteria": criteria,
            "candidate_records": batch,
            "required_output": {
                "included_candidate_ids": ["zero or more supplied IDs"],
                "extractions": [{"candidate_id": "supplied ID", "finding": "source-bounded finding", "certainty": "high/moderate/low/very low/unclear"}],
            },
            "evidence_ceiling": case.get("reproduction_ceiling", "metadata_and_abstract_only"),
        })
        screening_audits.append(screening_audit)
        batch_ids = {str(item["id"]) for item in batch}
        batch_proposed = screening_raw.get("included_candidate_ids", []) if screening_raw else []
        if not isinstance(batch_proposed, list) or not all(isinstance(value, str) for value in batch_proposed):
            invalid_batches += 1
            continue
        unknown.extend(value for value in batch_proposed if value not in batch_ids)
        verified_batch = list(dict.fromkeys(value for value in batch_proposed if value in batch_ids))
        proposed.extend(batch_proposed)
        included_now = set(verified_batch)
        raw_extractions = screening_raw.get("extractions", []) if screening_raw else []
        if isinstance(raw_extractions, list):
            extractions.extend(
                item for item in raw_extractions
                if isinstance(item, dict) and item.get("candidate_id") in included_now
                and isinstance(item.get("finding"), str) and bool(item["finding"].strip())
            )
    included = list(dict.fromkeys(value for value in proposed if value in visible_ids))
    screening_status = "completed" if invalid_batches == 0 else "completed_with_schema_abstention_batches"
    screening = {
        "status": screening_status,
        "visible_candidate_ids": visible_ids,
        "included_candidate_ids": included,
        "extractions": extractions,
        "verification_audit": {
            "requested": len(proposed), "verified": len(included), "unknown_ids": unknown,
            "batch_count": len(batches), "schema_invalid_batches": invalid_batches,
        },
    }

    synthesis_raw, synthesis_audit = _call_json(provider, {
        "stage": "evidence_synthesis",
        "question": case["operational_question"],
        "protocol": protocol,
        "verified_extractions": extractions,
        "required_output": {
            "claims": [{
                "statement": "evidence-bounded statement",
                "supporting_candidate_ids": ["one or more verified extraction IDs"],
                "certainty": "high/moderate/low/very low/unclear",
            }],
            "limitations": ["material limitations"],
        },
        "abstain_if_unsupported": True,
    })
    synthesis_initial_shape = _shape_signature(synthesis_raw)
    synthesis_repair_audit = None
    synthesis_repaired = False
    if not _synthesis_contract(synthesis_raw):
        synthesis_raw, synthesis_repair_audit = _call_json(provider, {
            "stage": "synthesis_schema_repair",
            "invalid_output": synthesis_raw,
            "invalid_output_shape": synthesis_initial_shape,
            "required_output": {
                "claims": [{
                    "statement": "evidence-bounded statement",
                    "supporting_candidate_ids": ["one or more verified extraction IDs"],
                    "certainty": "high/moderate/low/very low/unclear",
                }],
                "limitations": ["zero or more material limitations"],
            },
            "verified_candidate_ids": sorted({str(item["candidate_id"]) for item in extractions}),
            "instruction": "Repair structure only. Do not add claims, evidence, or candidate IDs.",
        })
        synthesis_repaired = _synthesis_contract(synthesis_raw)
    raw_claims = synthesis_raw.get("claims") if isinstance(synthesis_raw, dict) else None
    if not _synthesis_contract(synthesis_raw):
        synthesis = {"status": "abstained_provider_schema_invalid", "conclusion_statements": [], "certainty": "unclear", "limitations": ["invalid provider schema"]}
    else:
        extracted_ids = {str(item["candidate_id"]) for item in extractions}
        verified_claims = []
        unsupported_claims = 0
        invalid_claims = 0
        for claim in raw_claims:
            if (
                not isinstance(claim, dict)
                or not isinstance(claim.get("statement"), str)
                or not claim["statement"].strip()
                or not isinstance(claim.get("supporting_candidate_ids"), list)
                or not claim["supporting_candidate_ids"]
                or not all(isinstance(value, str) for value in claim["supporting_candidate_ids"])
                or not isinstance(claim.get("certainty"), str)
            ):
                invalid_claims += 1
                continue
            support = list(dict.fromkeys(claim["supporting_candidate_ids"]))
            if not set(support).issubset(extracted_ids):
                unsupported_claims += 1
                continue
            verified_claims.append({
                "statement": claim["statement"].strip(),
                "supporting_candidate_ids": support,
                "certainty": claim["certainty"].strip(),
            })
        synthesis = {
            "status": (
                "completed_after_schema_repair" if synthesis_repaired and invalid_claims == 0 else
                "completed" if invalid_claims == 0 else
                "completed_with_schema_abstention_claims"
            ),
            "claims": verified_claims,
            "conclusion_statements": [claim["statement"] for claim in verified_claims],
            "certainty": verified_claims[0]["certainty"] if verified_claims else "unclear",
            "limitations": synthesis_raw["limitations"],
            "verification_audit": {
                "requested_claims": len(raw_claims),
                "verified_claims": len(verified_claims),
                "unsupported_claims": unsupported_claims,
                "schema_invalid_claims": invalid_claims,
            },
        }
    audits = [protocol_audit]
    if protocol_repair_audit is not None:
        audits.append(protocol_repair_audit)
    audits.extend(screening_audits)
    audits.append(synthesis_audit)
    if synthesis_repair_audit is not None:
        audits.append(synthesis_repair_audit)
    return {
        "schema_version": "1.0-development",
        "plan_id": plan_id,
        "case_id": case["case_id"],
        "configuration_id": configuration["configuration_id"],
        "seed": seed,
        "capabilities": {
            "topic_opportunity_control": configuration["topic_opportunity_control"],
            "conclusion_directed_acquisition": configuration["conclusion_directed_acquisition"],
        },
        "protocol": protocol,
        "screening": screening,
        "synthesis": synthesis,
        "schema_diagnostics": {
            "protocol": {
                "initial_shape": protocol_initial_shape,
                "repair_attempted": protocol_repair_audit is not None,
                "repair_succeeded": protocol_repaired,
                "final_shape": _shape_signature(protocol_raw),
            },
            "synthesis": {
                "initial_shape": synthesis_initial_shape,
                "repair_attempted": synthesis_repair_audit is not None,
                "repair_succeeded": synthesis_repaired,
                "final_shape": _shape_signature(synthesis_raw),
            },
        },
        "provider_calls": len(audits),
        "input_tokens": sum(int(audit.get("prompt_tokens") or 0) for audit in audits),
        "output_tokens": sum(int(audit.get("completion_tokens") or 0) for audit in audits),
        "cost": None,
        "cost_status": "unknown",
        "wall_seconds": time.perf_counter() - started,
        "provider_audits": audits,
        "published_reference_accessed": False,
    }


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _tokens(values: Any) -> set[str]:
    text = values if isinstance(values, str) else " ".join(str(item) for item in values)
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def _framework_similarity(predicted: dict[str, Any], reference: dict[str, Any]) -> float:
    values = []
    for field in FRAMEWORK_FIELDS:
        left = predicted.get(field, [])
        right = reference.get(field, [])
        if field == "synthesis_route":
            values.append(float(_normal(str(left)) == _normal(str(right))))
            continue
        left_set = _tokens(left)
        right_set = _tokens(right)
        values.append(
            2 * len(left_set & right_set) / (len(left_set) + len(right_set))
            if left_set or right_set else 0.0
        )
    return sum(values) / len(values)


def score_reconstruction_output(output: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """Score only after the controller has unlocked the published reference."""
    predicted_framework = output.get("protocol", {}).get("question_framework", {})
    framework = _framework_similarity(predicted_framework, reference["question_framework"])
    predicted_ids = set(output.get("screening", {}).get("included_candidate_ids", []))
    visible_ids = set(output.get("screening", {}).get("visible_candidate_ids", predicted_ids))
    reference_ids = set(reference.get("included_candidate_ids", []))
    visible_reference_ids = visible_ids & reference_ids
    acquisition_recall = len(visible_reference_ids) / len(reference_ids) if reference_ids else 0.0
    recall = len(predicted_ids & reference_ids) / len(reference_ids) if reference_ids else 0.0
    conditional_recall = (
        len(predicted_ids & visible_reference_ids) / len(visible_reference_ids)
        if visible_reference_ids else 0.0
    )
    precision = len(predicted_ids & reference_ids) / len(predicted_ids) if predicted_ids else 0.0
    statements = " ".join(output.get("synthesis", {}).get("conclusion_statements", [])).casefold()
    axes = reference.get("conclusion_axes", [])
    recovered = [
        axis["axis_id"] for axis in axes
        if any(_normal(term) in statements for term in axis["required_terms_any"])
    ]
    axis_coverage = len(recovered) / len(axes) if axes else 0.0
    return {
        "case_id": output["case_id"],
        "configuration_id": output["configuration_id"],
        "seed": output["seed"],
        "framework_similarity": framework,
        "acquisition_recall": acquisition_recall,
        "screening_recall_conditional_on_visible": conditional_recall,
        "screening_recall": recall,
        "screening_precision": precision,
        "conclusion_axis_coverage": axis_coverage,
        "recovered_conclusion_axis_ids": recovered,
        "end_to_end_min_stage_score": min(framework, acquisition_recall, conditional_recall, axis_coverage),
    }
