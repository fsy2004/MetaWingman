"""Orchestrate one evidence-grounded joint question and synthesis design."""

from __future__ import annotations

from typing import Any

from .model_provider import ModelProvider
from .question_synthesis_agents import run_question_role
from .question_synthesis_search import finalize_question_portfolio, start_question_synthesis_search
from .question_synthesis_verifier import require_hard_verifiers, verify_question_candidate
from .synthesis_method_router import enumerate_synthesis_routes


def _with_execution_identity(
    result: dict[str, Any],
    *,
    configuration_id: str,
    seed: int,
    model: str,
) -> dict[str, Any]:
    role_runs = result.get("role_runs", [])
    model_calls = sum(int(item.get("attempts", 0)) for item in role_runs)
    result["configuration_id"] = configuration_id
    result["seed"] = seed
    result["same_provider_roles_are_independent_evidence"] = False
    result["execution_receipt"] = {
        "configuration_id": configuration_id,
        "seed": seed,
        "provider_seed_supported": False,
        "seed_scope": "orchestration_order_and_tie_breaks",
        "model_reference": model,
        "model_calls": model_calls,
        "status": result["status"],
        "same_provider_roles_are_independent_evidence": False,
    }
    return result


def design_review_question(
    *,
    provider: ModelProvider,
    landscape: dict[str, Any],
    context: dict[str, Any],
    routes: list[dict[str, Any]],
    budget: dict[str, Any],
    model: str,
    max_tokens: int,
    created_at_utc: str,
    role_sequence: list[str] | None = None,
    configuration_id: str = "full-biomedical-stack",
    seed: int = 20260820,
) -> dict[str, Any]:
    if configuration_id != "full-biomedical-stack":
        raise ValueError("joint design orchestrator is only the full-biomedical-stack arm")
    sequence = role_sequence or ["proposer", "opposition", "judge"]
    if not sequence or sequence[0] != "proposer":
        raise ValueError("role sequence must begin with proposer")
    proposer = run_question_role(
        provider,
        "proposer",
        {"landscape": landscape, "clinical_context": context, "method_routes": routes, "budget": budget},
        model=model,
        max_tokens=max_tokens,
    )
    if proposer["status"] != "candidate_generated":
        return _with_execution_identity(
            {"status": "abstained", "reason_codes": proposer["reason_codes"], "role_runs": [proposer]},
            configuration_id=configuration_id,
            seed=seed,
            model=model,
        )
    candidate = proposer["document"]
    role_runs = [proposer]
    route_decision = enumerate_synthesis_routes(context, candidate, routes, created_at_utc=created_at_utc)
    observations = verify_question_candidate(candidate, landscape, route_decision)
    for role in sequence[1:]:
        run = run_question_role(
            provider,
            role,
            {"candidate": candidate, "route_decision": route_decision, "verifier_observations": observations},
            model=model,
            max_tokens=max_tokens,
        )
        role_runs.append(run)
        if run["status"] == "abstained":
            return _with_execution_identity(
                {"status": "abstained", "reason_codes": [f"{role}_abstained"], "role_runs": role_runs, "route_decision": route_decision, "verifier_observations": observations},
                configuration_id=configuration_id,
                seed=seed,
                model=model,
            )
        revised = run.get("document", {}).get("candidate")
        if not isinstance(revised, dict):
            return _with_execution_identity(
                {
                    "status": "abstained",
                    "reason_codes": [f"{role}_candidate_missing"],
                    "role_runs": role_runs,
                    "route_decision": route_decision,
                    "verifier_observations": observations,
                },
                configuration_id=configuration_id,
                seed=seed,
                model=model,
            )
        candidate = revised
        route_decision = enumerate_synthesis_routes(context, candidate, routes, created_at_utc=created_at_utc)
        observations = verify_question_candidate(candidate, landscape, route_decision)
    route_decision = enumerate_synthesis_routes(context, candidate, routes, created_at_utc=created_at_utc)
    observations = verify_question_candidate(candidate, landscape, route_decision)
    require_hard_verifiers(observations)
    search = start_question_synthesis_search(landscape, context, [candidate], budget, created_at_utc=created_at_utc)
    portfolio = finalize_question_portfolio(search, updated_at_utc=created_at_utc)
    return _with_execution_identity(
        {
            "status": "selected",
            "candidate": candidate,
            "route_decision": route_decision,
            "verifier_observations": observations,
            "search": portfolio,
            "role_runs": role_runs,
        },
        configuration_id=configuration_id,
        seed=seed,
        model=model,
    )
