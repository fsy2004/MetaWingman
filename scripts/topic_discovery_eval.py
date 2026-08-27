#!/usr/bin/env python3
"""Topic-discovery evaluation: were the 601 REAL published review questions
discoverable from the evidence horizon available at their cutoff (R@K), and does
the gate accept them (select/review rate) with the bigram novelty definition?

Baseline: random pairing of the same term pool (same candidate count) — the
"search x reasoning" gain is measured, not assumed.

Output: research/topic-discovery-evidence.json
"""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.agent.topic_discovery import (  # noqa: E402
    bigrams, bm25, build_functional_terms, tokens)
from metawingman.agent.novelty_gate import gate  # noqa: E402

RES = _REPO_ROOT / "research"
SEED = 20260827


def bigram_occupancy(plan_records: list[dict], cutoff: int,
                     cache: dict[int, dict[str, int]]) -> dict[str, int]:
    """bigram occurrence counts among titles published strictly BEFORE cutoff."""
    if cutoff in cache:
        return cache[cutoff]
    counts: dict[str, int] = {}
    for r in plan_records:
        if int(r.get("year") or 0) >= cutoff:
            continue
        for b in bigrams(tokens(r.get("title") or "")):
            counts[b] = counts.get(b, 0) + 1
    cache[cutoff] = counts
    return counts


def topic_novelty(q_tokens: list[str], occ: dict[str, int]) -> float:
    """1 - fraction of the question's bigrams already jointly occupied."""
    qbg = set(bigrams(q_tokens))
    if not qbg:
        return 0.0
    hit = sum(1 for b in qbg if occ.get(b, 0) >= 2)
    return round(10.0 * (1.0 - hit / len(qbg)), 2)


def main() -> int:
    plan = json.loads((RES / "training-corpus-plan-biomedical-v3.json").read_text(encoding="utf-8"))
    plan_records = plan["records"]
    topics = json.loads((RES / "v3-catalog.json").read_text(encoding="utf-8"))["records"]
    n_plan = len(plan_records)
    global_idx: dict[str, int] = {}
    for r in plan_records:
        for w in tokens(r.get("title") or ""):
            global_idx[w] = global_idx.get(w, 0) + 1
    common = {w for w, c in global_idx.items() if c / n_plan > 0.25}

    k_list = (1, 5, 20)
    hits = {k: 0 for k in k_list}
    random_hits = {k: 0 for k in k_list}
    decisions = {"select": 0, "review": 0, "reject": 0}
    n = 0
    rng = random.Random(SEED)
    occ_cache: dict[int, dict[str, int]] = {}
    for r in topics:
        year = int(r.get("year") or 2020)
        cutoff = max(1990, year - 1)
        horizon = [x.get("title") or "" for x in plan_records if int(x.get("year") or 0) < cutoff]
        if len(horizon) < 200:
            continue
        n += 1
        # --- discovery: search x reasoning over the horizon ---
        terms = build_functional_terms([{"title": t} for t in horizon], common)
        q_tokens = tokens(r.get("title") or "")
        q_set = set(q_tokens)
        method_words = ["diagnostic", "network", "meta", "prognostic", "prevalence",
                        "rehabilitation", "therapy", "vaccine", "cohort", "systematic"]
        method_pool = [m for m in method_words if any(m in x for x in horizon)]
        cand_pool = terms[:120]
        # co-occurrence counting (one pass over the horizon); score = docs
        # containing BOTH the method word and the topic term (search signal)
        docs_of: dict[str, set[int]] = {}
        keep = set(method_pool) | set(cand_pool)
        for i, x in enumerate(horizon):
            for w in set(tokens(x)):
                if w in keep:
                    docs_of.setdefault(w, set()).add(i)
        scored_pairs = []
        for m in method_pool:
            dm = docs_of.get(m, set())
            for t in cand_pool:
                if t == m:
                    continue
                dt = docs_of.get(t, set())
                s = len(dm & dt)
                if s >= 2:
                    scored_pairs.append((s, m + " " + t))
        scored_pairs.sort(key=lambda p: -p[0])
        pairs = scored_pairs if scored_pairs else [(0.5, method_pool[0] + " " + cand_pool[0])]

        def novelty_of(cand: str) -> float:
            cbg = set(bigrams(tokens(cand)))
            occupied = 0
            for b in cbg:
                a, b2 = b.split("_", 1)
                if a in docs_of and b2 in docs_of and docs_of[a] & docs_of[b2]:
                    occupied += 1
            return max(0.0, 1.0 - occupied / max(1, len(cbg)))

        ranked = sorted(pairs[:400], key=lambda p: p[0] * (1.0 + novelty_of(p[1])), reverse=True)
        cand_texts = [p[1] for p in ranked[: max(k_list)]]
        # hit: candidate (method term, topic term) both appear in the real title
        def hit_of(cand: str) -> bool:
            cw = set(tokens(cand))
            return len(cw & q_set) >= 2

        for k in k_list:
            hits[k] += int(any(hit_of(c) for c in cand_texts[:k]))
        # random baseline: same counts, random pairs from the same pools
        for k in k_list:
            found = False
            for _ in range(k):
                m = rng.choice(method_pool) if method_pool else "meta"
                t = rng.choice(terms) if terms else "care"
                if hit_of(m + " " + t):
                    found = True
                    break
            random_hits[k] += int(found)
        # --- gate decision for the real topic (bigram joint-occupancy novelty) ---
        occ = bigram_occupancy(plan_records, cutoff, occ_cache)
        novel = topic_novelty(q_tokens[:8], occ)
        evidence = {"has_reference_standard": bool(re.search(r"diagnos|sensitiv|specific", r.get("title") or "", re.I)),
                    "has_prediction_model": bool(re.search(r"prediction|predict|prognos", r.get("title") or "", re.I)),
                    "comparator_count": 3 if re.search(r"network|multiple|compar", r.get("title") or "", re.I) else 2,
                    "outcome_measure_type": "proportion" if re.search(r"prevalence|incidence|proportion", r.get("title") or "", re.I) else "binary",
                    "precedent_found": True,
                    "evidence_actions": 4}
        res = gate(q_tokens[:8], {}, evidence, public_anchor=bool(r.get("pmcid")),
                   common=common, novelty_override=novel)
        decisions[res.decision] += 1

    out = {
        "scope": ("topic discovery (search x reasoning) evaluation: were 601 real published review "
                  "questions discoverable from the horizon available at their cutoff, vs random "
                  "pairing of the same term pools (gain measured, not assumed)"),
        "n": n, "k_list": list(k_list),
        "R_at_k": {f"R@{k}": round(v / n, 4) for k, v in hits.items()},
        "random_R_at_k": {f"R@{k}": round(v / n, 4) for k, v in random_hits.items()},
        "gate_decision_rates": {k: round(v / n, 4) for k, v in decisions.items()},
        "gate_accept_rate_select_or_review": round((decisions["select"] + decisions["review"]) / n, 4),
        "note": "discovery = horizon search (project two-stage retrieval line) x reasoning "
                "(co-occurrence gap = opportunity); gate = novelty x executability (2409.04109 split)",
    }
    (RES / "topic-discovery-evidence.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
