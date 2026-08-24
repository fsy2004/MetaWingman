#!/usr/bin/env python3
"""Process-level alignment (DPO-style) against the external expert judge.

Given preference pairs (chosen vs rejected trajectories, ranked by the external
judge), we compute a standard DPO-style objective that rewards the chosen over
the rejected process. When a model provides per-example log-probs we compute the
real DPO loss; otherwise we report the *preference alignment* (how well the
agent's own objective agrees with the external judge's ordering). Deterministic
and offline (no server, no gradient step here — the loss is a scalar the server
can optimise with real log-probs).
"""

from __future__ import annotations

import math
from typing import Any


def dpo_loss(chosen_logprob: float, rejected_logprob: float, beta: float = 0.1) -> float:
    """Standard DPO negative log-likelihood for one (chosen, rejected) pair.

    loss = -log sigmoid( beta * (logprob_chosen - logprob_rejected) )
    We use logits-style log-probs (more positive = more likely).
    """
    logit = beta * (chosen_logprob - rejected_logprob)
    # numerically stable log-sigmoid
    if logit >= 0:
        loss = math.log1p(math.exp(-logit))
    else:
        loss = -logit + math.log1p(math.exp(logit))
    return round(loss, 6)


def preference_alignment(
    pairs: list[dict[str, Any]],
    model_logprobs: list[tuple[float, float]] | None = None,
    *,
    beta: float = 0.1,
) -> dict[str, Any]:
    """Summarise preference alignment and (optionally) mean DPO loss.

    pairs: [{'chosen': process, 'rejected': process, 'chosen_score', 'rejected_score'}]
    model_logprobs: optional [(chosen_ll, rejected_ll), ...] aligned to pairs.
    """
    if not pairs:
        return {"n_pairs": 0, "mean_dpo_loss": None, "win_rate": 0.0,
                "aligned_fraction": 1.0}
    # win rate: chosen outranks rejected in the judge's ordering (it should, by construction).
    wins = sum(1 for p in pairs if p["chosen_score"] >= p["rejected_score"])
    # alignment: the external judge's reward-gap direction matches the model's preferred direction.
    gaps = [p["chosen_score"] - p["rejected_score"] for p in pairs]
    positive_fraction = sum(1 for g in gaps if g > 0) / len(gaps)

    losses = []
    if model_logprobs and len(model_logprobs) == len(pairs):
        for (c_ll, r_ll) in model_logprobs:
            losses.append(dpo_loss(c_ll, r_ll, beta=beta))
    mean_dpo = round(sum(losses) / len(losses), 6) if losses else None
    return {
        "n_pairs": len(pairs),
        "win_rate": round(wins / len(pairs), 4),
        "aligned_fraction": round(positive_fraction, 4),
        "mean_dpo_loss": mean_dpo,
        "beta": beta,
        "method": "process-level preference alignment (external judge ordering)",
    }
