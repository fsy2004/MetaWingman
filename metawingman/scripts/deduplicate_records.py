#!/usr/bin/env python3
"""Conservative exact deduplication; fuzzy matches are review candidates only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path


def norm_id(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().lower())


def norm_doi(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .")


def norm_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


class UnionFind:
    def __init__(self, n: int): self.parent = list(range(n))
    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]; x = self.parent[x]
        return x
    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a != b: self.parent[b] = a


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--fuzzy-threshold", type=float, default=0.93)
    args = parser.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle); rows = list(reader); fields = reader.fieldnames or []
    uf = UnionFind(len(rows)); seen: dict[tuple[str, str], int] = {}; reasons = defaultdict(set)
    exact_fields = [("doi", norm_doi), ("pmid", norm_id), ("pmcid", norm_id), ("nct_id", norm_id), ("title", norm_title)]
    for idx, row in enumerate(rows):
        for field, normalizer in exact_fields:
            value = normalizer(row.get(field, ""))
            if not value or (field == "title" and len(value) < 20): continue
            key = (field, value)
            if key in seen:
                other = seen[key]; uf.union(idx, other); reasons[(idx, other)].add(field)
            else:
                seen[key] = idx
    groups = defaultdict(list)
    for idx in range(len(rows)): groups[uf.find(idx)].append(idx)
    deduped, mapping = [], []
    for number, members in enumerate(groups.values(), 1):
        canonical = max(members, key=lambda i: sum(bool(rows[i].get(f, "")) for f in fields))
        merged = dict(rows[canonical]); merged["record_id"] = f"dedup:{number:07d}"
        merged["member_record_ids"] = ";".join(rows[i].get("record_id", str(i)) for i in members)
        merged["sources"] = ";".join(sorted({rows[i].get("source", "") for i in members if rows[i].get("source", "")}))
        deduped.append(merged)
        for i in members:
            mapping.append({"original_record_id": rows[i].get("record_id", str(i)), "deduplicated_record_id": merged["record_id"], "group_size": len(members), "automatic_basis": "exact identifier/title" if len(members) > 1 else "unique"})
    candidates = []
    title_buckets = defaultdict(list)
    for group_idx, row in enumerate(deduped):
        title = norm_title(row.get("title", ""))
        if len(title) >= 20: title_buckets[title[:1]].append((group_idx, title))
    for bucket in title_buckets.values():
        for pos, (i, a) in enumerate(bucket):
            for j, b in bucket[pos + 1:]:
                if abs(len(a) - len(b)) > max(20, int(0.25 * max(len(a), len(b)))): continue
                ratio = SequenceMatcher(None, a, b).ratio()
                if ratio >= args.fuzzy_threshold:
                    candidates.append({"candidate_id": f"cand:{len(candidates)+1:07d}", "record_id_a": deduped[i]["record_id"], "record_id_b": deduped[j]["record_id"], "match_basis": "fuzzy_title_candidate_only", "similarity": f"{ratio:.4f}", "reviewer_decision": "", "reviewer": "", "date": ""})
    out_fields = fields + [x for x in ["member_record_ids", "sources"] if x not in fields]
    for path, data, fieldnames in [
        (args.outdir / "records_deduplicated.csv", deduped, out_fields),
        (args.outdir / "dedup_map.csv", mapping, list(mapping[0]) if mapping else ["original_record_id", "deduplicated_record_id", "group_size", "automatic_basis"]),
        (args.outdir / "dedup_candidates.csv", candidates, ["candidate_id", "record_id_a", "record_id_b", "match_basis", "similarity", "reviewer_decision", "reviewer", "date"]),
    ]:
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore"); writer.writeheader(); writer.writerows(data)
    audit = {"input_file": str(args.input.resolve()), "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(), "input_records": len(rows), "output_records": len(deduped), "exact_duplicates_removed": len(rows) - len(deduped), "fuzzy_candidates_not_removed": len(candidates), "rule": "DOI/PMID/PMCID/NCT/exact normalized title only; fuzzy matches require human review"}
    (args.outdir / "dedup_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(audit))
    return 0


if __name__ == "__main__": raise SystemExit(main())
