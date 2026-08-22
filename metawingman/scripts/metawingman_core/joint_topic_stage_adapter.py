"""Direct candidate-generation adapter for the joint lifecycle topic stage."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .deterministic_topic_signal_audit import build_deterministic_topic_signal_audit
from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError, MeteredModelProvider
from .provider_factory import build_provider
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json
from .topic_external_search import build_topic_audit_queries, compile_topic_external_search_receipt
from .topic_opportunity import select_topic_portfolio
from .topic_proposer import propose_topics
from .topic_signal_audit import landscape_node_ids, promote_proposal_after_independent_audit


ProviderBuilder = Callable[[dict[str, Any]], Any]
ExternalSearcher = Callable[..., dict[str, dict[str, Any]]]
ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, binding: dict[str, Any], label: str) -> Path:
    path = (root / str(binding.get("path") or "")).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file():
        raise JointLifecycleRunError(f"{label} is missing")
    if _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} hash drift")
    return path


def _artifact(path: Path, artifact_id: str, role: str) -> dict[str, str]:
    return {
        "artifact_id": artifact_id,
        "path": str(path.resolve()),
        "sha256": _sha(path),
        "media_type": "application/json",
        "role": role,
    }


def _pubmed_ids(query: str, maximum_records: int) -> list[str]:
    url = ESEARCH + "?" + urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": str(maximum_records), "retmode": "json",
    })
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return [str(value) for value in payload.get("esearchresult", {}).get("idlist", [])]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last = exc
            if attempt < 3:
                time.sleep(2 * attempt)
    raise JointLifecycleRunError(f"PubMed opposition search failed after three attempts: {last}")


def run_pubmed_topic_opposition(
    proposal: dict[str, Any],
    landscape: dict[str, Any],
    *,
    lower_date: str,
    maximum_records: int,
) -> dict[str, dict[str, Any]]:
    queries = build_topic_audit_queries(
        proposal,
        cutoff_date=landscape["corpus_boundary"]["cutoff_date"],
        lower_date=lower_date,
        landscape=landscape,
    )
    return {
        kind: {"query": query, "pmids": _pubmed_ids(query, maximum_records)}
        for kind, query in queries.items()
    }


def _selected_record(
    proposal: dict[str, Any], *, candidate_id: str | None, basis: str,
) -> dict[str, Any]:
    return {
        "proposal_id": proposal["proposal_id"],
        "candidate_id": candidate_id,
        "question_framework": proposal["question_framework"],
        "evidence_node_ids": proposal["evidence_node_ids"],
        "selection_basis": basis,
    }


def execute_topic_feasibility_stage(
    request: dict[str, Any],
    meter: AtomicStageBudgetMeter,
    *,
    provider_builder: ProviderBuilder = build_provider,
    external_searcher: ExternalSearcher = run_pubmed_topic_opposition,
) -> dict[str, Any]:
    """Generate candidates independently in each arm and select without target access."""
    if request.get("stage_id") != "topic_feasibility" or request.get("ordinal") != 0:
        raise JointLifecycleRunError("topic adapter can execute only canonical stage zero")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("topic adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_topic_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    topic_inputs = {
        item["binding_id"]: item for item in request.get("topic_inputs", [])
        if isinstance(item, dict) and isinstance(item.get("binding_id"), str)
    }
    landscape_binding = topic_inputs.get("temporal_evidence_landscape")
    if landscape_binding is None:
        raise JointLifecycleRunError("temporal evidence landscape binding is missing")
    landscape_path = _resolve(root, landscape_binding, "temporal evidence landscape")
    try:
        landscape = json.loads(landscape_path.read_text(encoding="utf-8"))
        validate_document(landscape, "temporal_evidence_landscape")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid temporal evidence landscape: {exc}") from exc
    provider_path = _resolve(root, config["provider_config"], "provider config")
    try:
        provider_config = json.loads(provider_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JointLifecycleRunError("provider config is not valid JSON") from exc
    provider = MeteredModelProvider(
        provider_builder(provider_config),
        meter,
        max_input_tokens_per_call=config["maximum_input_tokens_per_call"],
    )
    decision_control = request.get("topic_opportunity_control") is True
    expected_mode = (
        "decision_aware_direct_generation" if decision_control else "generic_direct_generation"
    )
    if request.get("candidate_generation_mode") != expected_mode:
        raise JointLifecycleRunError("topic arm and candidate-generation mode disagree")
    proposal_batch = propose_topics(
        landscape,
        provider,
        maximum_proposals=config["maximum_proposals"],
        maximum_prompt_characters=config["maximum_prompt_characters"],
        thinking=config["thinking"],
        generation_mode="decision_aware" if decision_control else "generic_direct",
        created_at_utc=request["created_at_utc"],
    )
    if proposal_batch["model_provenance"]["model"] != "deepseek-v4-flash":
        raise JointLifecycleRunError("topic stage must use the frozen deepseek-v4-flash model")
    proposal_path = output_dir / "proposal-batch.json"
    atomic_write_json(proposal_path, proposal_batch, "topic_proposal_batch")
    artifacts = [_artifact(proposal_path, "proposal_batch", "direct_candidate_generation")]
    selected: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    if not decision_control:
        if proposal_batch["status"] == "proposals_generated" and proposal_batch["proposals"]:
            selected = [
                _selected_record(
                    proposal_batch["proposals"][0],
                    candidate_id=None,
                    basis="generic_llm_order",
                )
            ]
            reason_codes = ["generic_direct_generation_selected_first_valid_proposal"]
        else:
            reason_codes = ["generic_direct_generation_returned_no_valid_proposal"]
        selection_policy = "generic_llm_order"
    else:
        receipts: list[dict[str, Any]] = []
        audits: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        failures: list[dict[str, str]] = []
        provider_id = proposal_batch["model_provenance"]["model"]
        for proposal in proposal_batch["proposals"]:
            try:
                raw = external_searcher(
                    proposal,
                    landscape,
                    lower_date=config["external_search_lower_date"],
                    maximum_records=config["external_search_maximum_records"],
                )
                receipt = compile_topic_external_search_receipt(proposal, landscape, raw)
                audit = build_deterministic_topic_signal_audit(
                    proposal,
                    landscape,
                    receipt,
                    proposal_provider_id=provider_id,
                    auditor_id=config["auditor_id"],
                )
                candidate = promote_proposal_after_independent_audit(
                    proposal,
                    audit,
                    proposal_provider_id=provider_id,
                    landscape_id=landscape["landscape_id"],
                    landscape_node_ids=landscape_node_ids(landscape),
                    created_at_utc=request["created_at_utc"],
                )
                receipts.append(receipt)
                audits.append(audit)
                candidates.append(candidate)
            except Exception as exc:
                failures.append({
                    "proposal_id": str(proposal.get("proposal_id")),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })
        receipt_path = output_dir / "external-search-receipts.json"
        audit_path = output_dir / "topic-signal-audits.json"
        candidate_path = output_dir / "topic-candidates.json"
        failure_path = output_dir / "topic-audit-failures.json"
        atomic_write_json(receipt_path, receipts)
        atomic_write_json(audit_path, audits)
        atomic_write_json(candidate_path, candidates)
        atomic_write_json(failure_path, failures)
        artifacts.extend((
            _artifact(receipt_path, "external_search_receipts", "independent_opposition_search"),
            _artifact(audit_path, "signal_audits", "deterministic_topic_signal_audit"),
            _artifact(candidate_path, "topic_candidates", "audited_topic_candidates"),
            _artifact(failure_path, "topic_audit_failures", "retained_topic_audit_failures"),
        ))
        decision = select_topic_portfolio(
            landscape, candidates, created_at_utc=request["created_at_utc"],
        )
        decision_path = output_dir / "topic-decision.json"
        atomic_write_json(decision_path, decision, "topic_opportunity_decision")
        artifacts.append(_artifact(
            decision_path, "topic_decision", "decision_opportunity_control",
        ))
        by_candidate = {
            f"candidate-{proposal['proposal_id']}": proposal
            for proposal in proposal_batch["proposals"]
        }
        portfolio_selected = [
            _selected_record(
                by_candidate[candidate_id],
                candidate_id=candidate_id,
                basis="decision_opportunity_control",
            )
            for candidate_id in decision["selected_candidate_ids"]
            if candidate_id in by_candidate
        ]
        selected = portfolio_selected[:1]
        reason_codes = list(decision["reason_codes"])
        if len(portfolio_selected) > 1:
            reason_codes.append("single_review_slot_uses_top_ranked_selected_candidate")
        if failures:
            reason_codes.append("proposal_audit_failures_retained")
        selection_policy = "decision_opportunity_control"

    state = {
        "schema_version": "1.0",
        "stage_id": "topic_feasibility",
        "case_id": request["case_id"],
        "arm_id": request["arm_id"],
        "seed": request["seed"],
        "generation_mode": expected_mode,
        "proposal_batch_sha256": _sha(proposal_path),
        "selection_policy": selection_policy,
        "selected_proposals": selected,
        "status": "selected" if selected else "abstained",
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "published_reference_accessed": False,
    }
    try:
        validate_document(state, "joint_topic_stage_state")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    state_path = output_dir / "topic-state.json"
    atomic_write_json(state_path, state, "joint_topic_stage_state")
    artifacts.append(_artifact(state_path, "topic_state", "stage_state"))
    status = "completed" if selected else "abstained"
    checks = [
        {
            "check_id": "direct_candidate_generation",
            "status": "passed" if proposal_batch["proposals"] else "abstained",
            "evidence_artifact_ids": ["proposal_batch", "topic_state"],
        },
        {
            "check_id": (
                "decision_opportunity_control" if decision_control
                else "generic_candidate_generation"
            ),
            "status": "passed" if selected else "abstained",
            "evidence_artifact_ids": ["topic_state"],
        },
    ]
    output = {
        "schema_version": "1.0",
        "stage_id": "topic_feasibility",
        "status": status,
        "state_artifact_id": "topic_state",
        "artifacts": artifacts,
        "scientific_checks": checks,
        "terminal_reason": None if selected else "no_topic_passed_the_arm_specific_selection_rule",
    }
    try:
        validate_document(output, "joint_lifecycle_stage_output")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    return output


def topic_feasibility_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter,
) -> dict[str, Any]:
    """Public frozen adapter binding used by the joint lifecycle runner."""
    return execute_topic_feasibility_stage(request, meter)
