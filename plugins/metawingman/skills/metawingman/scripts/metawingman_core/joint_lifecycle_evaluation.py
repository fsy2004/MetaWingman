"""Semantic hard gates for preregistered joint lifecycle evaluations.

The JSON schema deliberately permits explicit ``missing`` and ``blocked``
states.  This module turns those scientifically incomplete states into
machine-readable blockers and never opens a sealed published reference.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .schema_guard import SchemaValidationError, validate_document


CANONICAL_STAGE_IDS = (
    "topic_feasibility",
    "protocol_registration",
    "search_retrieval",
    "selection",
    "data_lineage",
    "appraisal",
    "freeze_synthesis",
    "certainty_interpretation",
    "reporting_review",
    "living_update",
)
FROZEN_SEEDS = (20260820, 20260821, 20260822)
TOPIC_INPUT_IDS = (
    "temporal_evidence_landscape",
    "topic_generation_protocol",
    "topic_signal_audit_protocol",
    "topic_scoring_protocol",
)
MECHANISM_BINDING_IDS = (
    "topic_candidate_generator",
    "topic_opportunity_controller",
    "conclusion_risk_impact_controller",
)
VERSION_GRAPH_ROLES = (
    "historical_cutoff",
    "operational_corpus",
    "screening_workbook",
    "published_article",
    "published_conclusions",
)
CHECKPOINT_ROLES = ("query_encoder", "document_encoder")


class JointLifecyclePlanError(ValueError):
    """Raised when a plan cannot be audited without ambiguity."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_relative(root: Path, value: str) -> Path | None:
    candidate = (root / value).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return candidate


def _audit_file_binding(
    binding: dict[str, Any], *, root: Path, label: str, blockers: list[str],
) -> bool:
    if binding.get("status") != "locked":
        blockers.append(f"file_binding_unlocked:{label}")
        return False
    path_value = binding.get("path")
    expected = binding.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str):
        blockers.append(f"file_binding_incomplete:{label}")
        return False
    path = _resolve_relative(root, path_value)
    if path is None:
        blockers.append(f"file_path_outside_repository:{label}")
        return False
    if not path.is_file():
        blockers.append(f"file_missing:{label}")
        return False
    if _sha256(path) != expected:
        blockers.append(f"file_hash_drift:{label}")
        return False
    return True


def _receipt_identity(receipt: dict[str, Any]) -> tuple[str, str, int, str]:
    return (
        str(receipt.get("case_slot_id")),
        str(receipt.get("arm_id")),
        int(receipt.get("seed")),
        str(receipt.get("stage_id")),
    )


def _identity_text(identity: tuple[str, str, int, str]) -> str:
    return "/".join(str(value) for value in identity)


def _audit_resource_usage(
    usage: dict[str, Any], *, identity: str, locked_receipt: bool,
    blockers: list[str],
) -> bool:
    valid = True
    for name in ("provider_calls", "input_tokens", "output_tokens"):
        record = usage[name]
        status, value = record["status"], record["value"]
        if status == "observed" and value is None:
            blockers.append(f"resource_observation_missing:{identity}:{name}")
            valid = False
        if status == "not_applicable" and value not in {None, 0}:
            blockers.append(f"resource_not_applicable_has_value:{identity}:{name}")
            valid = False
        if locked_receipt and status not in {"observed", "not_applicable"}:
            blockers.append(f"locked_receipt_resource_not_terminal:{identity}:{name}")
            valid = False

    wall = usage["wall_seconds"]
    if wall["status"] == "observed" and wall["value"] is None:
        blockers.append(f"resource_observation_missing:{identity}:wall_seconds")
        valid = False
    if wall["status"] == "not_applicable" and wall["value"] not in {None, 0}:
        blockers.append(f"resource_not_applicable_has_value:{identity}:wall_seconds")
        valid = False
    if locked_receipt and wall["status"] not in {"observed", "not_applicable"}:
        blockers.append(f"locked_receipt_resource_not_terminal:{identity}:wall_seconds")
        valid = False

    cost = usage["cost"]
    cost_status, cost_value = cost["status"], cost["value"]
    calls = usage["provider_calls"]
    if cost_status == "known" and (cost_value is None or cost["currency"] is None):
        blockers.append(f"known_cost_value_or_currency_missing:{identity}")
        valid = False
    if cost_status in {"unknown", "not_applicable"} and cost_value is not None:
        blockers.append(f"null_cost_policy_violated:{identity}")
        valid = False
    if cost_status == "not_applicable" and not (
        calls["status"] == "not_applicable"
        or (calls["status"] == "observed" and calls["value"] == 0)
    ):
        blockers.append(f"resource_cost_not_applicable_with_provider_calls:{identity}")
        valid = False
    if locked_receipt and cost_status not in {"known", "unknown", "not_applicable"}:
        blockers.append(f"locked_receipt_resource_not_terminal:{identity}:cost")
        valid = False
    return valid


def _unique(values: list[str], label: str) -> None:
    if len(values) != len(set(values)):
        raise JointLifecyclePlanError(f"duplicate {label}")


def audit_joint_lifecycle_plan(
    plan: dict[str, Any], *, repository_root: Path | None = None,
) -> dict[str, Any]:
    """Audit a joint evaluation plan without opening sealed references.

    Structurally valid plans may remain scientifically blocked.  Unsafe order,
    identity, or factorial ambiguities raise :class:`JointLifecyclePlanError`;
    missing artifacts and unfinished scientific prerequisites are returned as
    blockers so an orchestrator can stop without pretending the run is ready.
    """
    try:
        validate_document(plan, "joint_lifecycle_evaluation_plan")
    except (FileNotFoundError, SchemaValidationError) as exc:
        raise JointLifecyclePlanError(str(exc)) from exc
    root = (
        repository_root.resolve(strict=False)
        if repository_root is not None
        else Path(__file__).resolve().parents[3]
    )
    blockers: list[str] = []

    stages = plan["lifecycle_stages"]
    stage_ids = tuple(item["stage_id"] for item in stages)
    ordinals = tuple(item["ordinal"] for item in stages)
    if stage_ids != CANONICAL_STAGE_IDS or ordinals != tuple(range(10)):
        raise JointLifecyclePlanError(
            "lifecycle stages must be the exact ten stages in canonical order"
        )
    if tuple(plan["seeds"]) != FROZEN_SEEDS:
        raise JointLifecyclePlanError("seeds must equal the three frozen seeds in order")

    ledger_binding = plan["innovation_ledger_reference"]
    ledger_verified = _audit_file_binding(
        ledger_binding, root=root, label="innovation_ledger_reference", blockers=blockers,
    )

    topic_inputs = plan["topic_protocol_inputs"]
    topic_ids = tuple(item["binding_id"] for item in topic_inputs)
    if topic_ids != TOPIC_INPUT_IDS:
        raise JointLifecyclePlanError(
            "topic protocol inputs must bind landscape, generation, audit, and scoring protocols in canonical order"
        )
    for item in topic_inputs:
        label = f"topic_input:{item['binding_id']}"
        if item["status"] != "locked" or not _audit_file_binding(
            item, root=root, label=label, blockers=[],
        ):
            blockers.append(f"topic_protocol_input_unlocked:{item['binding_id']}")

    mechanisms = plan["mechanism_bindings"]
    mechanism_ids = [item["binding_id"] for item in mechanisms]
    _unique(mechanism_ids, "mechanism binding")
    if tuple(mechanism_ids) != MECHANISM_BINDING_IDS:
        raise JointLifecyclePlanError(
            "actual candidate generator, topic controller, and risk-impact controller are required"
        )
    verified_mechanisms: list[str] = []
    for item in mechanisms:
        binding_id = item["binding_id"]
        cli_ok = _audit_file_binding(
            item["cli"], root=root,
            label=f"mechanism:{binding_id}:cli", blockers=blockers,
        )
        implementation_ok = _audit_file_binding(
            item["implementation"], root=root,
            label=f"mechanism:{binding_id}:implementation", blockers=blockers,
        )
        if cli_ok and implementation_ok:
            verified_mechanisms.append(binding_id)

    prerequisite_ids = [item["prerequisite_id"] for item in plan["scientific_prerequisites"]]
    _unique(prerequisite_ids, "scientific prerequisite")
    for prerequisite in plan["scientific_prerequisites"]:
        if prerequisite["status"] != "satisfied":
            blockers.append(
                f"scientific_prerequisite_{prerequisite['status']}:"
                f"{prerequisite['prerequisite_id']}"
            )

    design = plan["evaluation_design"]
    if design["candidate_comparison_scope"] != "direct_candidate_generation_per_arm":
        blockers.append("shared_candidate_reranking_is_not_direct_baseline")
    budget = design["matched_budget"]
    required_budget_fields = (
        "max_provider_calls", "max_input_tokens", "max_output_tokens", "wall_seconds",
    )
    if budget["status"] != "frozen" or any(
        budget[field] is None or budget[field] <= 0 for field in required_budget_fields
    ):
        blockers.append("matched_resource_budget_unfrozen")

    arms = design["arms"]
    arm_ids = [item["arm_id"] for item in arms]
    _unique(arm_ids, "arm_id")
    capability_pairs = {
        (item["topic_opportunity_control"], item["conclusion_risk_impact_control"])
        for item in arms
    }
    if capability_pairs != {(False, False), (True, False), (False, True), (True, True)}:
        raise JointLifecyclePlanError("evaluation arms must form the exact two-by-two factorial")
    for arm in arms:
        topic_expected = (
            "decision_aware_direct_generation"
            if arm["topic_opportunity_control"] else "generic_direct_generation"
        )
        acquisition_expected = (
            "risk_times_impact"
            if arm["conclusion_risk_impact_control"] else "fixed_generic"
        )
        if arm["candidate_generation_mode"] != topic_expected:
            blockers.append(f"arm_topic_mode_mismatch:{arm['arm_id']}")
        if arm["acquisition_mode"] != acquisition_expected:
            blockers.append(f"arm_acquisition_mode_mismatch:{arm['arm_id']}")
        _audit_file_binding(
            arm["runner_binding"], root=root,
            label=f"arm_runner:{arm['arm_id']}", blockers=blockers,
        )
        _audit_resource_usage(
            arm["resource_usage"], identity=f"arm:{arm['arm_id']}",
            locked_receipt=False, blockers=blockers,
        )

    expected_checkpoints = {
        (seed, role) for seed in FROZEN_SEEDS for role in CHECKPOINT_ROLES
    }
    observed_checkpoints = {
        (item["seed"], item["role"]) for item in plan["checkpoint_records"]
    }
    if observed_checkpoints != expected_checkpoints:
        raise JointLifecyclePlanError(
            "checkpoint records must contain query and document encoders for every frozen seed"
        )
    checkpoint_complete = True
    for checkpoint in plan["checkpoint_records"]:
        label = f"checkpoint:{checkpoint['checkpoint_id']}"
        binding = {
            "status": checkpoint["status"],
            "path": checkpoint["artifact_path"],
            "sha256": checkpoint["artifact_sha256"],
        }
        if not _audit_file_binding(binding, root=root, label=label, blockers=[]):
            checkpoint_complete = False
        if checkpoint["training_manifest_sha256"] is None or checkpoint["family_manifest_sha256"] is None:
            checkpoint_complete = False
    if not checkpoint_complete:
        blockers.append("checkpoint_records_incomplete")

    cases = plan["cases"]
    slot_ids = [item["case_slot_id"] for item in cases]
    _unique(slot_ids, "case_slot_id")
    if len(cases) < plan["case_admission_policy"]["minimum_confirmatory_cases"]:
        blockers.append("confirmatory_case_count_below_frozen_minimum")
    admitted_profiles: set[tuple[str, ...]] = set()
    case_by_slot = {item["case_slot_id"]: item for item in cases}
    for case in cases:
        slot_id = case["case_slot_id"]
        if case["admission_status"] != "admitted" or case["case_id"] is None:
            blockers.append(f"case_slot_not_admitted:{slot_id}")
        if case["authority_status"] != "verified_primary":
            blockers.append(f"case_authority_not_verified:{slot_id}")
        if case["representativeness_status"] != "verified":
            blockers.append(f"case_representativeness_not_verified:{slot_id}")
        if case["prior_target_exposure_status"] != "none":
            blockers.append(f"case_prior_target_exposure_unresolved:{slot_id}")
        if not case["profile_strata"]:
            blockers.append(f"case_profile_strata_unresolved:{slot_id}")
        else:
            admitted_profiles.add(tuple(sorted(case["profile_strata"])))

        graph = case["version_graph"]
        graph_nodes = graph["nodes"]
        roles = tuple(node["role"] for node in graph_nodes)
        if roles != VERSION_GRAPH_ROLES:
            raise JointLifecyclePlanError(
                f"{slot_id}: case version graph must bind the exact five canonical roles"
            )
        expected_edges = set(VERSION_GRAPH_ROLES[1:])
        observed_edges = {edge["to_role"] for edge in graph["edges"]}
        if observed_edges != expected_edges:
            raise JointLifecyclePlanError(
                f"{slot_id}: case version graph cutoff edges are incomplete"
            )
        graph_complete = graph["status"] == "locked"
        for node in graph_nodes:
            role = node["role"]
            if role == "historical_cutoff":
                if node["cutoff_exact"] is not True or node["cutoff_value"] is None:
                    graph_complete = False
            elif node["cutoff_exact"] is not None or node["cutoff_value"] is not None:
                graph_complete = False
            if role in {"published_article", "published_conclusions"}:
                if (
                    node["status"] != "sealed_locked"
                    or node["path"] is not None
                    or node["sha256"] is None
                    or node["exposure"] != "sealed_controller_only"
                ):
                    graph_complete = False
                if node["path"] is not None:
                    blockers.append(f"sealed_locator_exposed_in_operational_plan:{slot_id}:{role}")
            else:
                binding = {
                    "status": "locked" if node["status"] == "operational_locked" else "missing",
                    "path": node["path"],
                    "sha256": node["sha256"],
                }
                if not _audit_file_binding(
                    binding, root=root, label=f"case:{slot_id}:{role}", blockers=[],
                ):
                    graph_complete = False
        if not graph_complete:
            blockers.append(f"case_version_graph_unbound:{slot_id}")

    if (
        plan["case_admission_policy"]["materially_different_review_profiles_required"]
        and len(admitted_profiles) < len(cases)
    ):
        blockers.append("confirmatory_review_profiles_not_materially_distinct")

    closures = plan["family_closures"]
    closure_slots = [item["case_slot_id"] for item in closures]
    _unique(closure_slots, "family closure case_slot_id")
    if set(closure_slots) != set(slot_ids):
        raise JointLifecyclePlanError("family closures must map exactly one-to-one to case slots")
    closures_locked = True
    for closure in closures:
        case = case_by_slot[closure["case_slot_id"]]
        complete = all((
            closure["status"] == "locked",
            closure["review_family_id"] is not None,
            closure["review_family_id"] == case["review_family_id"],
            closure["training_family_manifest_sha256"] is not None,
            closure["dependency_closure_sha256"] is not None,
            closure["closed_at_utc"] is not None,
        ))
        closures_locked = closures_locked and complete
    if not closures_locked:
        blockers.append("family_closures_open")

    expected_receipts = {
        (slot_id, arm_id, seed, stage_id)
        for slot_id in slot_ids
        for arm_id in arm_ids
        for seed in FROZEN_SEEDS
        for stage_id in CANONICAL_STAGE_IDS
    }
    observed_receipts: set[tuple[str, str, int, str]] = set()
    valid_locked_receipts: set[tuple[str, str, int, str]] = set()
    for receipt in plan["stage_receipts"]:
        identity = _receipt_identity(receipt)
        identity_label = _identity_text(identity)
        if identity in observed_receipts:
            blockers.append(f"duplicate_stage_receipt:{identity_label}")
            continue
        observed_receipts.add(identity)
        if identity not in expected_receipts:
            blockers.append(f"unexpected_stage_receipt:{identity_label}")
            continue
        if receipt["status"] != "locked":
            continue
        hashes_complete = all(
            receipt[field] is not None
            for field in ("checkpoint_sha256", "input_manifest_sha256", "output_manifest_sha256")
        )
        if not hashes_complete:
            blockers.append(f"locked_stage_receipt_hash_missing:{identity_label}")
        resources_complete = _audit_resource_usage(
            receipt["resource_usage"], identity=identity_label,
            locked_receipt=True, blockers=blockers,
        )
        if hashes_complete and resources_complete:
            valid_locked_receipts.add(identity)

    expected_count = len(expected_receipts)
    locked_count = len(valid_locked_receipts)
    receipts_locked = valid_locked_receipts == expected_receipts
    if not receipts_locked:
        blockers.append(f"stage_receipts_incomplete:{locked_count}/{expected_count}")

    unlock_allowed = receipts_locked and closures_locked
    gate = plan["published_reference_gate"]
    if not unlock_allowed:
        blockers.append("published_reference_unlock_gate_not_satisfied")
    if gate["state"] == "unsealed" and not unlock_allowed:
        blockers.append("premature_published_reference_unseal")
    if gate["state"] == "unsealed" and gate["unsealed_at_utc"] is None:
        blockers.append("published_reference_unseal_timestamp_missing")
    if gate["state"] == "sealed" and gate["unsealed_at_utc"] is not None:
        blockers.append("sealed_reference_has_unseal_timestamp")

    blockers = list(dict.fromkeys(blockers))
    scientifically_ready = not blockers
    if scientifically_ready and unlock_allowed:
        status = "all_stage_receipts_locked"
    elif scientifically_ready:
        status = "ready_to_execute"
    else:
        status = "blocked_not_run"
    return {
        "schema_valid": True,
        "plan_id": plan["plan_id"],
        "declared_status": plan["plan_status"],
        "status": status,
        "scientifically_ready": scientifically_ready,
        "innovation_ledger_reference": {
            "path": ledger_binding.get("path"),
            "sha256": ledger_binding.get("sha256"),
            "verified": ledger_verified,
        },
        "mechanism_bindings": {
            "required": list(MECHANISM_BINDING_IDS),
            "verified": verified_mechanisms,
        },
        "stage_receipts": {
            "expected": expected_count,
            "observed": len(observed_receipts),
            "locked": locked_count,
        },
        "family_closures": {
            "expected": len(cases),
            "locked": sum(closure["status"] == "locked" for closure in closures),
            "complete": closures_locked,
        },
        "published_reference_gate": {
            "state": gate["state"],
            "unlock_allowed": unlock_allowed,
            "reference_was_opened": gate["state"] == "unsealed",
        },
        "resource_fields": list(plan["resource_accounting_policy"]["required_fields"]),
        "scientific_blockers": blockers,
        "declared_blockers": list(plan["declared_blockers"]),
    }
