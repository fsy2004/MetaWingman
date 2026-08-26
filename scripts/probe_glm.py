#!/usr/bin/env python3
"""Diagnose the GLM provider: one chat call, print the raw content (and error).
Run with GLM_API_KEY set in the environment (never in the repo)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metawingman.scripts.metawingman_core.provider_factory import build_provider, load_provider_config

BASE = ["intervention_pairwise", "intervention_network", "diagnostic_accuracy",
        "prognostic_prediction", "prevalence_incidence", "public_health_exposure",
        "structured_no_pooling"]
SYSTEM = ("You are a senior systematic-review methodologist. Given a clinical question "
          "and the evidence structure, decide which review design a top-journal systematic "
          "review would use. Answer with ONLY ONE of: " + ", ".join(BASE) + ".")
USER = ('{"question": {"type": "intervention", "intervention_count": 6, "is_living_or_update": true}, '
        '"evidence_structure": {"comparator_count": 8, "arms_per_study": 3, "outcome_unit": "binary", '
        '"is_update": true, "n_nodes_assessed": true}}')


def main() -> int:
    provider = build_provider(load_provider_config(Path("metawingman/references/glm-provider-config.json")))
    print("provider:", provider.credential_source)
    print("models:", provider.list_models())
    try:
        res = provider.chat([{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": USER}],
                            json_output=False, max_tokens=400)
        print("finish_reason:", res.finish_reason)
        print("content:", repr(res.content[:300]))
    except Exception as exc:
        print("ERROR:", type(exc).__name__, str(exc)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
