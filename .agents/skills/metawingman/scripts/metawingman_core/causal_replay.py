"""Evaluate single-change protocol stress tests with intervention replay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .schema_guard import SchemaValidationError, validate_document
from .state_store import sha256_json


class CausalReplayError(ValueError):
    """Raised when a counterfactual case is structurally incoherent."""


def _unique(items: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item[key]
        if value in index:
            raise CausalReplayError(f"duplicate {label}: {value}")
        index[value] = item
    return index


def _derive_delta(node: dict[str, Any]) -> str:
    if node["abstained"]:
        if not node["abstention_reason"]:
            raise CausalReplayError(
                f"node {node['node_id']} abstained without an abstention_reason"
            )
        return "abstained"
    base = node["base_artifact_sha256"]
    counterfactual = node["counterfactual_artifact_sha256"]
    if base is None and counterfactual is None:
        raise CausalReplayError(
            f"node {node['node_id']} has neither base nor counterfactual artifact"
        )
    if base is None:
        return "added"
    if counterfactual is None:
        return "removed"
    if base == counterfactual:
        return "unchanged"
    return "changed"


def _validate_references(case: dict[str, Any]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    expected = _unique(case["expected_node_deltas"], "node_id", "expected node_id")
    observed = _unique(case["observed_node_deltas"], "node_id", "observed node_id")
    events = _unique(case["event_trace"], "event_id", "event_id")
    _unique(case["event_trace"], "sequence", "event sequence")
    _unique(case["replay_interventions"], "replay_id", "replay_id")

    for node_id, item in expected.items():
        if item["gold_basis"] != "synthetic_fixture" and not item["anchor_ids"]:
            raise CausalReplayError(
                f"gold node {node_id} requires at least one evidence anchor"
            )

    unknown_observed = sorted(set(observed) - set(expected))
    if unknown_observed:
        raise CausalReplayError(f"observed nodes are absent from the gold delta set: {unknown_observed}")

    sequence_by_event = {event_id: item["sequence"] for event_id, item in events.items()}
    for event_id, event in events.items():
        unknown_nodes = sorted(set(event["affected_node_ids"]) - set(expected))
        if unknown_nodes:
            raise CausalReplayError(
                f"event {event_id} affects nodes absent from the gold delta set: {unknown_nodes}"
            )
        unknown_predecessors = sorted(set(event["predecessor_event_ids"]) - set(events))
        if unknown_predecessors:
            raise CausalReplayError(
                f"event {event_id} has unknown predecessors: {unknown_predecessors}"
            )
        non_prior = sorted(
            predecessor
            for predecessor in event["predecessor_event_ids"]
            if sequence_by_event[predecessor] >= event["sequence"]
        )
        if non_prior:
            raise CausalReplayError(
                f"event {event_id} has non-prior predecessors: {non_prior}"
            )

    replay_variants: set[tuple[str, str]] = set()
    for replay in case["replay_interventions"]:
        if replay["event_id"] not in events:
            raise CausalReplayError(
                f"replay {replay['replay_id']} targets unknown event {replay['event_id']}"
            )
        variant_key = (replay["event_id"], replay["event_order_variant"])
        if variant_key in replay_variants:
            raise CausalReplayError(
                "duplicate event-order variant for event "
                f"{replay['event_id']}: {replay['event_order_variant']}"
            )
        replay_variants.add(variant_key)
        replay_nodes = _unique(
            replay["resulting_node_deltas"], "node_id", f"replay {replay['replay_id']} node_id"
        )
        unknown_nodes = sorted(set(replay_nodes) - set(expected))
        if unknown_nodes:
            raise CausalReplayError(
                f"replay {replay['replay_id']} contains nodes absent from the gold delta set: {unknown_nodes}"
            )
        for node in replay_nodes.values():
            _derive_delta(node)
    for node in observed.values():
        _derive_delta(node)
    return expected, observed, events


def _boundary_reasons(case: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    protocol = case["protocol"]
    intervention = case["intervention"]
    boundary = case["boundary"]
    if protocol["base_sha256"] == protocol["counterfactual_sha256"]:
        reasons.append("protocol_artifacts_are_identical")
    if sha256_json(intervention["base_value"]) == sha256_json(intervention["counterfactual_value"]):
        reasons.append("intervention_values_are_identical")
    if not intervention["single_change_verified"]:
        reasons.append("single_change_not_verified")
    if not boundary["source_corpus_frozen"]:
        reasons.append("source_corpus_not_frozen")
    if not boundary["protocol_variants_frozen_before_run"]:
        reasons.append("protocol_variants_not_frozen_before_run")
    if boundary["run_context"] == "historical_reconstruction":
        if not boundary["answers_sealed"]:
            reasons.append("historical_answers_not_sealed")
        if not boundary["post_cutoff_evidence_sealed"]:
            reasons.append("historical_post_cutoff_evidence_not_sealed")
        if boundary["leakage_audit"] != "passed":
            reasons.append("historical_leakage_audit_not_passed")
    return reasons


def evaluate_causal_replay(
    case: dict[str, Any],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Score protocol adherence and replay-supported event responsibility.

    The attribution is limited to the sealed software execution graph. It is not
    a causal claim about medicine, treatment effects, or the underlying evidence.
    """
    try:
        validate_document(case, "protocol_counterfactual_case")
    except SchemaValidationError as exc:
        raise CausalReplayError(str(exc)) from exc
    expected, observed, events = _validate_references(case)
    timestamp = created_at_utc or datetime.now(timezone.utc).isoformat()
    reasons = _boundary_reasons(case)
    valid_case = not reasons

    node_results: list[dict[str, Any]] = []
    for node_id, gold in expected.items():
        observation = observed.get(node_id)
        observed_status = _derive_delta(observation) if observation else "missing"
        node_results.append({
            "node_id": node_id,
            "expected_status": gold["expected_status"],
            "observed_status": observed_status,
            "match": observed_status == gold["expected_status"],
        })
    node_results.sort(key=lambda item: item["node_id"])
    mismatched = [item for item in node_results if not item["match"]]
    mismatch_ids = {item["node_id"] for item in mismatched}
    matched_count = len(node_results) - len(mismatched)
    metrics = {
        "expected": len(expected),
        "observed": len(observed),
        "matched": matched_count,
        "mismatched": len(mismatched),
        "delta_accuracy": round(matched_count / len(expected), 8),
    }

    candidate_events = sorted(
        (
            event for event in events.values()
            if event["verification_status"] in {"failed", "abstained"}
            and set(event["affected_node_ids"]) & mismatch_ids
        ),
        key=lambda item: (item["sequence"], item["event_id"]),
    )
    earliest = candidate_events[0] if candidate_events else None
    earliest_summary = None
    if earliest:
        earliest_summary = {
            "event_id": earliest["event_id"],
            "sequence": earliest["sequence"],
            "stage": earliest["stage"],
            "verification_status": earliest["verification_status"],
        }

    replay_results: list[dict[str, Any]] = []
    if earliest:
        eligible_replays = [
            replay for replay in case["replay_interventions"]
            if replay["event_id"] == earliest["event_id"]
            and replay["replacement_verified"]
            and replay["downstream_replay_complete"]
        ]
        for replay in sorted(eligible_replays, key=lambda item: item["replay_id"]):
            replay_nodes = {
                item["node_id"]: _derive_delta(item)
                for item in replay["resulting_node_deltas"]
            }
            recovered = sorted(
                node_id for node_id in mismatch_ids
                if node_id in replay_nodes
                and replay_nodes[node_id] == expected[node_id]["expected_status"]
            )
            unrecovered = sorted(mismatch_ids - set(recovered))
            replay_results.append({
                "replay_id": replay["replay_id"],
                "event_id": replay["event_id"],
                "event_order_variant": replay["event_order_variant"],
                "recovery_rate": round(len(recovered) / len(mismatch_ids), 8),
                "recovered_node_ids": recovered,
                "unrecovered_node_ids": unrecovered,
            })

    if not valid_case:
        adherence = "invalid"
        attribution = "invalid"
        stability = "invalid"
    elif not mismatched:
        adherence = "passed"
        attribution = "not_needed"
        stability = "not_applicable"
    else:
        adherence = "failed"
        reasons.append("protocol_delta_mismatch")
        if not earliest:
            attribution = "not_testable"
            stability = "not_tested"
            reasons.append("earliest_failed_event_not_exposed")
        elif not replay_results:
            attribution = "not_testable"
            stability = "not_tested"
            reasons.append("verified_complete_replay_missing")
        else:
            recovery_signatures = {
                tuple(result["recovered_node_ids"])
                for result in replay_results
            }
            eligible_by_id = {item["replay_id"]: item for item in eligible_replays}
            replacement_hashes = {
                eligible_by_id[result["replay_id"]]["replacement_output_sha256"]
                for result in replay_results
            }
            stability = (
                "not_tested" if len(replay_results) == 1
                else "stable" if len(recovery_signatures) == 1 and len(replacement_hashes) == 1
                else "unstable"
            )
            rates = [result["recovery_rate"] for result in replay_results]
            if all(rate == 1.0 for rate in rates) and stability == "stable":
                attribution = "supported"
            elif all(rate == 1.0 for rate in rates):
                attribution = "partial"
                reasons.append("event_order_stability_not_tested")
            elif any(rate > 0 for rate in rates):
                attribution = "partial"
                reasons.append("replay_recovery_partial_or_unstable")
            else:
                attribution = "not_supported"
                reasons.append("replay_did_not_recover_expected_deltas")

    if attribution == "supported":
        interpretation = (
            f"Replacing verified output at event {earliest['event_id']} recovered all discrepant "
            "node deltas within this sealed execution graph. This supports software-event "
            "responsibility, not biomedical or scientific causality."
        )
    elif attribution == "not_needed":
        interpretation = (
            "Observed downstream deltas matched the frozen counterfactual gold set; no error "
            "intervention was needed."
        )
    elif attribution == "invalid":
        interpretation = (
            "The counterfactual boundary is invalid, so neither protocol adherence nor error "
            "attribution is interpretable."
        )
    else:
        interpretation = (
            "The run contains protocol-delta errors, but replay does not fully and stably support "
            "responsibility of a single software event."
        )

    report = {
        "schema_version": "1.0",
        "case_id": case["case_id"],
        "case_sha256": sha256_json(case),
        "valid_case": valid_case,
        "reason_codes": sorted(set(reasons)),
        "protocol_adherence_status": adherence,
        "node_metrics": metrics,
        "node_results": node_results,
        "earliest_candidate_event": earliest_summary,
        "replay_results": replay_results,
        "causal_attribution_status": attribution,
        "stability_status": stability,
        "interpretation": interpretation,
        "created_at_utc": timestamp,
    }
    try:
        validate_document(report, "causal_replay_report")
    except SchemaValidationError as exc:
        raise CausalReplayError(str(exc)) from exc
    return report
