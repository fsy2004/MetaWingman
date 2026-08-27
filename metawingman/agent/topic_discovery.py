#!/usr/bin/env python3
"""Topic discovery engine: search x reasoning on the evidence horizon.

Design (top-venue analogues): two-stage retrieval exists in the project
(tools/bm25-two-stage-retrieval-eval.py; DPR/SBERT line) — stage 1 surfaces
candidate evidence; the discovery layer REASONS over the horizon: co-occurrence
bigrams form candidate question slots (topic x method/outcome), and a
time-bounded occupancy gap (search score of the combination among reviews
published before the cutoff) marks the opportunity. Evaluation follows the
retrieval-benchmark R@K convention (MetaSyn-style: was the real published
question discoverable from the horizon available at its cutoff?).

Deterministic, zero training; sources: project's own retrieval asset + the
retrieval-line literature already deep-read (MetaSyn R@K; OpenScholar
retriever+reasoning pattern).
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


def tokens(title: str) -> list[str]:
    t = re.sub(r"[^A-Za-z0-9 ]", " ", title).lower()
    return [w for w in t.split() if len(w) > 3]


def bigrams(words: list[str]) -> list[str]:
    return [a + "_" + b for a, b in zip(words, words[1:])]


def build_functional_terms(records: list[dict], common: set[str]) -> list[str]:
    """Domain words (frequency-ranked) that are NOT background terms."""
    cnt: Counter[str] = Counter()
    for r in records:
        for w in tokens(r.get("title") or ""):
            if w not in common:
                cnt[w] += 1
    return [w for w, c in cnt.most_common(400)]


def bm25(corpus_titles: list[str], terms: list[str], k: int = 5,
         avg_len: float | None = None, n_docs: int | None = None) -> list[tuple[int, float]]:
    """Tiny BM25 over title tokens (project's retrieval line, deterministic)."""
    n = len(corpus_titles)
    avg = avg_len or (sum(len(t.split()) for t in corpus_titles) / max(1, n))
    dfs = {t: sum(1 for x in corpus_titles if t in x.split()) for t in terms}
    scores = []
    for i, x in enumerate(corpus_titles):
        xs = x.split()
        s = 0.0
        for t in terms:
            f = xs.count(t)
            if f == 0:
                continue
            idf = math.log(1 + (n - dfs[t] + 0.5) / (dfs[t] + 0.5))
            s += idf * f * (2.2 + 1) / (f + 2.2 * (1 - 0.75 + 0.75 * len(xs) / avg))
        scores.append((i, s))
    scores.sort(key=lambda p: -p[1])
    return scores[:k]


@dataclass
class DiscoveredQuestion:
    topic: str
    method: str
    novelty: float
    executability: float
    score: float
    gone_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"topic": self.topic, "method": self.method, "novelty": round(self.novelty, 2),
                "executability": round(self.executability, 2), "score": round(self.score, 3)}
