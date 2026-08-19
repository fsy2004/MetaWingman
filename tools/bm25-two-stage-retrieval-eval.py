#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BM25-recall two-stage retrieval evaluation (direction fix after the
TF-IDF two-stage failed acceptance: docs/architecture/two-stage-retrieval-
results-2026-08-18.md recommended retesting the ceiling with a stronger
lexical recall (BM25) instead of a larger K).

Conventions identical to tools/two-stage-retrieval-eval.py:
  - query text        = instruction + " Review: " + review_title
  - documents         = dev_examples[i].input_text
  - positive for i    = dev_examples[i] itself
  - same-family docs  (j != i and family_id equal) masked to -inf
  - trained encoding  = CLS token, L2-normalized; queries 256 / docs 512
  - metrics           = MRR, Recall@10, Precision@1

Adds a scipy-sparse BM25 (k1=1.5, b=0.75, IDF smoothing) recall stage:
  1. BM25 top-K candidate sets per query (K in [50, 100, 200]) + recall
     ceilings (fraction of queries whose positive is inside BM25 top-K).
  2. Rerank with the trained model (CLS dot product).
  3. Report single-stage baselines (TF-IDF full, BM25 full, trained full)
     and two-stage numbers for BM25 recall (and TF-IDF recall for
     continuity).

Output: /root/autodl-tmp/bm25-two-stage-results.json
"""
import json
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
import torch
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from transformers import AutoModel, AutoTokenizer

ROOT = Path("/root/autodl-tmp/mw")
EXAMPLES = ROOT / "validation-output/training-corpus/training-examples.jsonl"
MODEL_FINAL = ROOT / "validation-output/training-runs/evidence-retrieval/final"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
OUT = Path("/root/autodl-tmp/bm25-two-stage-results.json")
KS = [50, 100, 200]
BM25_K1 = 1.5
BM25_B = 0.75


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def query_text(example):
    title = example.get("review_title") or ""
    return f"{example['instruction']} Review: {title}" if title else example["instruction"]


def metrics_from_rank(positions):
    mrr = float(np.mean([1.0 / p if p > 0 else 0.0 for p in positions]))
    recall_at_10 = float(np.mean([1.0 if 0 < p <= 10 else 0.0 for p in positions]))
    precision_at_1 = float(np.mean([1.0 if p == 1 else 0.0 for p in positions]))
    return {"mrr": round(mrr, 6), "recall_at_10": round(recall_at_10, 6), "precision_at_1": round(precision_at_1, 6)}


def build_bm25_matrix(queries, documents):
    """Return (query_counts csr, A csr) with A[t,d] = BM25 term weight of term t in doc d."""
    t0 = time.time()
    doc_cv = CountVectorizer(stop_words="english")
    doc_counts = doc_cv.fit_transform(documents)          # (n_docs, vocab) CSR
    q_cv = CountVectorizer(stop_words="english", vocabulary=doc_cv.vocabulary_)
    query_counts = q_cv.transform(queries)                 # (n_queries, vocab) CSR
    vocab_size = doc_counts.shape[1]
    n_docs = doc_counts.shape[0]
    df = np.bincount(doc_counts.indices, minlength=vocab_size).astype(np.float64)
    idf = np.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
    doc_len = np.asarray(doc_counts.sum(axis=1)).ravel()
    avgdl = float(doc_len.mean())

    data = doc_counts.data.astype(np.float64)
    rows = doc_counts.indices  # term ids (CSR column indices for a (doc, term) matrix)
    cols = doc_counts.indptr
    doc_idx_per_nnz = np.repeat(np.arange(n_docs), np.diff(cols))
    tf = data
    denom = tf + BM25_K1 * (1 - BM25_B + BM25_B * doc_len[doc_idx_per_nnz] / avgdl)
    values = idf[rows] * (tf * (BM25_K1 + 1.0)) / denom
    A = sp.csr_matrix((values, (rows, doc_idx_per_nnz)), shape=(vocab_size, n_docs))
    print(f"[bm25] A matrix {A.shape} nnz={A.nnz} in {time.time() - t0:.1f}s", flush=True)
    return query_counts.tocsr(), A.tocsr()


def sparse_row_scores(query_counts, A, i):
    row = query_counts.getrow(i)          # (1, vocab)
    return (row @ A).toarray().ravel()    # (n_docs,)


def main():
    t_start = time.time()
    examples = [e for e in load(EXAMPLES) if e.get("task") == "evidence_retrieval" and e.get("split") == "development"]
    queries = [query_text(e) for e in examples]
    documents = [e["input_text"] for e in examples]
    families = [e["family_id"] for e in examples]
    n = len(examples)
    print(f"[bm25-two-stage] dev retrieval examples: {n}", flush=True)
    family_arr = np.array(families)
    idx_arr = np.arange(n)

    # ---------- TF-IDF (continuity baseline) ----------
    t0 = time.time()
    vectorizer = TfidfVectorizer(stop_words="english")
    q = vectorizer.fit_transform(queries)
    d = vectorizer.transform(documents)
    sim = np.empty((n, n), dtype=np.float64)
    for i in range(n):
        sim[i] = (q.getrow(i) @ d.T).toarray()
    print(f"[bm25-two-stage] tfidf sim in {time.time() - t0:.1f}s", flush=True)

    # ---------- BM25 ----------
    query_counts, A = build_bm25_matrix(queries, documents)

    def masked(row, i):
        row = row.copy()
        row[(idx_arr != i) & (family_arr == families[i])] = -np.inf
        return row

    def positions_of(sim_fn):
        positions = np.zeros(n, dtype=np.int32)
        for i in range(n):
            row = masked(sim_fn(i), i)
            positions[i] = int(np.where(np.argsort(-row) == i)[0][0]) + 1
        return positions

    tfidf_full = metrics_from_rank(positions_of(lambda i: sim[i].copy()))
    print(f"[bm25-two-stage] tfidf full: {tfidf_full}", flush=True)

    bm25_scores_cache = {}
    t0 = time.time()
    bm25_full_pos = np.zeros(n, dtype=np.int32)
    for i in range(n):
        row = sparse_row_scores(query_counts, A, i)
        bm25_scores_cache[i] = row
        row = masked(row, i)
        bm25_full_pos[i] = int(np.where(np.argsort(-row) == i)[0][0]) + 1
    bm25_full = metrics_from_rank(bm25_full_pos.tolist())
    print(f"[bm25-two-stage] bm25 full: {bm25_full} in {time.time() - t0:.1f}s", flush=True)

    # ---------- BM25 top-K candidate sets + ceilings ----------
    topk_sets = {k: [] for k in KS}
    ceilings = {}
    for i in range(n):
        row = masked(bm25_scores_cache[i].copy(), i)
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
    print(f"[bm25-two-stage] BM25 ceilings: {json.dumps(ceilings)}", flush=True)

    # ---------- trained model encodings ----------
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_FINAL)
    model = AutoModel.from_pretrained(MODEL_FINAL).to(DEVICE)
    model.eval()

    def encode(texts, max_length, tag):
        vectors = []
        for start in range(0, len(texts), 32):
            batch = tokenizer(texts[start:start + 32], padding=True, truncation=True,
                              max_length=max_length, return_tensors="pt").to(DEVICE)
            with torch.no_grad():
                vectors.append(torch.nn.functional.normalize(model(**batch).last_hidden_state[:, 0], dim=-1))
        out = torch.cat(vectors)
        print(f"[bm25-two-stage] encoded {len(texts)} {tag} in {time.time() - t0:.1f}s", flush=True)
        return out

    query_vectors = encode(queries, 256, "queries")
    doc_vectors = encode(documents, 512, "documents")
    sims_t = (query_vectors @ doc_vectors.T).cpu().numpy().astype(np.float32)
    trained_positions = np.zeros(n, dtype=np.int32)
    for i in range(n):
        row = sims_t[i].copy()
        row[(idx_arr != i) & (family_arr == families[i])] = -np.inf
        trained_positions[i] = int(np.where(np.argsort(-row) == i)[0][0]) + 1
    trained_full = metrics_from_rank(trained_positions.tolist())
    print(f"[bm25-two-stage] trained full: {trained_full}", flush=True)

    # ---------- two-stage rerank (BM25 recall) ----------
    bm25_two_stage = {}
    for k in KS:
        t0 = time.time()
        positions = np.zeros(n, dtype=np.int32)
        for i in range(n):
            topk = topk_sets[k][i]
            topk_t = torch.as_tensor(topk, device=doc_vectors.device)
            scores = (query_vectors[i] @ doc_vectors[topk_t].T).cpu().numpy().ravel()
            order = np.argsort(-scores)
            if i in topk:
                positions[i] = int(np.where(order == np.where(topk == i)[0][0])[0][0]) + 1
            else:
                positions[i] = 0
        m = metrics_from_rank(positions.tolist())
        m.update(ceilings[k])
        bm25_two_stage[k] = m
        print(f"[bm25-two-stage] K={k}: {m} in {time.time() - t0:.1f}s", flush=True)

    results = {
        "n_queries": n,
        "model": str(MODEL_FINAL),
        "corpus": str(EXAMPLES),
        "bm25_params": {"k1": BM25_K1, "b": BM25_B, "idf": "log((N-df+0.5)/(df+0.5)+1)"},
        "k_values": KS,
        "metric_semantics": (
            "query i positive = dev_examples[i].input_text; same-family docs masked; "
            "MRR = mean(1/rank); Recall@10 / Precision@1 on the ranked list; positive "
            "missing from candidates counts as rank 0."
        ),
        "single_stage_tfidf_full": tfidf_full,
        "single_stage_bm25_full": bm25_full,
        "single_stage_trained_full": trained_full,
        "two_stage_bm25_recall": {str(k): bm25_two_stage[k] for k in KS},
        "elapsed_seconds": round(time.time() - t_start, 1),
    }
    OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[bm25-two-stage] DONE wrote " + str(OUT), flush=True)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
