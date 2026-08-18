#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Two-stage retrieval evaluation: TF-IDF recall stage -> 12k-retrained BiomedBERT rerank.

Runs on the MetaWingman training server (/root/autodl-tmp). Reuses the exact
conventions of /root/autodl-tmp/mw-baseline-v3.py:
  - query text        = instruction + " Review: " + review_title
  - documents         = dev_examples[i].input_text
  - positive for query i = dev_examples[i] itself
  - masking           = same-family docs (j != i and family_id equal) set to -inf
  - trained encoding  = CLS token, L2-normalized; queries max_len 256, docs max_len 512
  - metrics           = MRR = mean(1/rank), Recall@10, Precision@1

Two-stage protocol per query i and recall depth K in [50, 100, 200]:
  1. TF-IDF top-K candidate set from the masked similarity row (the positive
     doc i is kept in the candidate set when it ranks within top-K).
  2. Rerank the K candidates with the trained model (dot product of CLS vectors).
  3. Report MRR / R@10 / P@1 on the reranked K-list (positive missing from the
     candidate set contributes 0), plus the recall ceiling = fraction of queries
     whose positive was even inside the TF-IDF top-K.

The trained model is applied once to all queries and all documents and the
vectors cached, so the rerank is exactly equivalent to per-query candidate
encoding but avoids ~10,882 x K redundant forward passes.

Output: /root/autodl-tmp/two-stage-results.json (plus console prints).
"""
import json
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import AutoModel, AutoTokenizer

ROOT = Path("/root/autodl-tmp/mw")
EXAMPLES = ROOT / "validation-output/training-corpus/training-examples.jsonl"
MODEL_FINAL = ROOT / "validation-output/training-runs/evidence-retrieval/final"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT = Path("/root/autodl-tmp/two-stage-results.json")
KS = [50, 100, 200]


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def query_text(example):
    title = example.get("review_title") or ""
    return f"{example['instruction']} Review: {title}" if title else example["instruction"]


def metrics_from_rank(positions, n):
    """positions: 1-based rank of the positive per query; 0 => positive absent."""
    mrr = float(np.mean([1.0 / p if p > 0 else 0.0 for p in positions]))
    recall_at_10 = float(np.mean([1.0 if 0 < p <= 10 else 0.0 for p in positions]))
    precision_at_1 = float(np.mean([1.0 if p == 1 else 0.0 for p in positions]))
    return {
        "mrr": round(mrr, 6),
        "recall_at_10": round(recall_at_10, 6),
        "precision_at_1": round(precision_at_1, 6),
    }


def main():
    t_start = time.time()
    examples = [e for e in load(EXAMPLES) if e.get("task") == "evidence_retrieval" and e.get("split") == "development"]
    queries = [query_text(e) for e in examples]
    documents = [e["input_text"] for e in examples]
    families = [e["family_id"] for e in examples]
    n = len(examples)
    print(f"[two-stage] dev retrieval examples: {n}", flush=True)

    # ---------- TF-IDF full-corpus similarities (same vectorizer as baseline) ----------
    t0 = time.time()
    vectorizer = TfidfVectorizer(stop_words="english")
    q = vectorizer.fit_transform(queries)
    d = vectorizer.transform(documents)
    # Row-by-row matmul keeps peak memory bounded (no n x n intermediate).
    sim = np.empty((n, n), dtype=np.float64)
    for i in range(n):
        sim[i] = (q.getrow(i) @ d.T).toarray()
    print(f"[two-stage] tfidf sim matrix {sim.shape} in {time.time() - t0:.1f}s", flush=True)

    family_arr = np.array(families)
    idx_arr = np.arange(n)

    def masked_row(i):
        row = sim[i].copy()
        row[(idx_arr != i) & (family_arr == families[i])] = -np.inf
        return row

    # ---------- single-stage baseline: TF-IDF full-corpus ----------
    t0 = time.time()
    tfidf_positions = np.zeros(n, dtype=np.int32)
    for i in range(n):
        row = masked_row(i)
        tfidf_positions[i] = int(np.where(np.argsort(-row) == i)[0][0]) + 1
    tfidf_full = metrics_from_rank(tfidf_positions.tolist(), n)
    print(f"[two-stage] tfidf full: {tfidf_full} in {time.time() - t0:.1f}s", flush=True)

    # ---------- top-K candidate sets per query + recall ceilings ----------
    t0 = time.time()
    topk_sets = {k: [] for k in KS}
    ceilings = {}
    for i in range(n):
        row = masked_row(i)
        valid = np.where(row > -np.inf)[0]
        order = valid[np.argsort(-row[valid])]
        for k in KS:
            topk_sets[k].append(order[:k])
    for k in KS:
        n_in = int(np.sum([1 for i in range(n) if i in topk_sets[k][i]]))
        ceilings[k] = {
            "n_positive_in_topk": n_in,
            "n_positive_missing": n - n_in,
            "recall_ceiling": round(n_in / n, 6),
        }
    print(f"[two-stage] top-K sets + ceilings in {time.time() - t0:.1f}s: {json.dumps(ceilings)}", flush=True)

    # ---------- trained model: encode all queries + all documents once ----------
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_FINAL)
    model = AutoModel.from_pretrained(MODEL_FINAL).to(DEVICE)
    model.eval()
    print(f"[two-stage] model loaded in {time.time() - t0:.1f}s, device={DEVICE}", flush=True)

    def encode(texts, max_length, tag):
        vectors = []
        t = time.time()
        for start in range(0, len(texts), 32):
            batch = tokenizer(
                texts[start:start + 32], padding=True, truncation=True,
                max_length=max_length, return_tensors="pt",
            ).to(DEVICE)
            with torch.no_grad():
                vectors.append(torch.nn.functional.normalize(model(**batch).last_hidden_state[:, 0], dim=-1))
        out = torch.cat(vectors)
        print(f"[two-stage] encoded {len(texts)} {tag} (max_len={max_length}) in {time.time() - t:.1f}s", flush=True)
        return out

    query_vectors = encode(queries, 256, "queries")
    doc_vectors = encode(documents, 512, "documents")

    # ---------- single-stage baseline: trained model full-corpus ----------
    t0 = time.time()
    sims_t = (query_vectors @ doc_vectors.T).cpu().numpy().astype(np.float32)
    trained_positions = np.zeros(n, dtype=np.int32)
    for i in range(n):
        row = sims_t[i].copy()
        row[(idx_arr != i) & (family_arr == families[i])] = -np.inf
        trained_positions[i] = int(np.where(np.argsort(-row) == i)[0][0]) + 1
    trained_full = metrics_from_rank(trained_positions.tolist(), n)
    print(f"[two-stage] trained full: {trained_full} in {time.time() - t0:.1f}s", flush=True)

    # ---------- two-stage rerank per K ----------
    two_stage = {}
    for k in KS:
        t0 = time.time()
        positions = np.zeros(n, dtype=np.int32)
        for i in range(n):
            topk = topk_sets[k][i]
            topk_t = torch.as_tensor(topk, device=doc_vectors.device)
            cand_vecs = doc_vectors[topk_t]  # (k, 768) on device
            scores = (query_vectors[i] @ cand_vecs.T).cpu().numpy().ravel()
            order = np.argsort(-scores)
            if i in topk:
                positions[i] = int(np.where(order == np.where(topk == i)[0][0])[0][0]) + 1
            else:
                positions[i] = 0
        m = metrics_from_rank(positions.tolist(), n)
        m.update(ceilings[k])
        two_stage[k] = m
        print(f"[two-stage] K={k}: {m} in {time.time() - t0:.1f}s", flush=True)

    results = {
        "n_queries": n,
        "model": str(MODEL_FINAL),
        "corpus": str(EXAMPLES),
        "k_values": KS,
        "metric_semantics": (
            "query i positive = dev_examples[i].input_text; same-family docs "
            "(j != i, family_id equal) masked; MRR = mean(1/rank); Recall@10 / "
            "Precision@1 evaluated on the ranked list (full corpus for "
            "single-stage, top-K reranked candidates for two-stage; positive "
            "missing from candidates counts as rank 0)."
        ),
        "single_stage_tfidf_full": tfidf_full,
        "single_stage_trained_full": trained_full,
        "two_stage": {str(k): two_stage[k] for k in KS},
        "elapsed_seconds": round(time.time() - t_start, 1),
    }
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[two-stage] DONE wrote " + str(OUT), flush=True)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
