"""Generate the deterministic screening acceptance fixture (v2 preregistration).

30 records: 10 designed includes, 10 near-miss excludes, 5 exclude-rule hits,
3 no-rule matches, 2 abstain (missing title+abstract). Writes records JSONL +
an expected-decisions key derived from the SAME rules (rules are the fixture's
source of truth, as the preregistration states).
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
RULES = json.loads((OUT / "screening-criterion-anchors.json").read_text(encoding="utf-8"))

records = []
for i in range(1, 11):
    records.append({
        "id": f"fix-inc-{i:02d}",
        "title": f"Clinical accuracy of a rapid antigen diagnostic test for SARS-CoV-2: evaluation {i}",
        "abstract": "We evaluated sensitivity and specificity of an antigen rapid diagnostic test in symptomatic patients.",
    })
for i in range(1, 11):
    records.append({
        "id": f"fix-near-{i:02d}",
        "title": f"Rapid antigen testing logistics in SARS-CoV-2 screening programme {i}",
        "abstract": "Operational feasibility and turnaround time of test distribution.",
    })
for i in range(1, 6):
    records.append({
        "id": f"fix-excl-{i:02d}",
        "title": f"Antigen rapid diagnostic accuracy for SARS-CoV-2 in an animal model {i}",
        "abstract": "In vitro characterisation of assay binding in cell culture.",
    })
for i in range(1, 4):
    records.append({
        "id": f"fix-none-{i:02d}",
        "title": f"Logistics of diagnostic supply chains during a pandemic wave {i}",
        "abstract": "Distribution modelling of consumables.",
    })
records.append({"id": "fix-abstain-01", "title": "", "abstract": ""})
records.append({"id": "fix-abstain-02", "title": "   ", "abstract": " "})

records_path = OUT / "screening-records.jsonl"
records_path.write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
)

# Expected key: replay the same pure rules (import the engine).
import importlib.util
spec = importlib.util.spec_from_file_location(
    "run_screening_slice",
    Path(__file__).resolve().parents[3] / "metawingman" / "scripts" / "run_screening_slice.py",
)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
result = engine.screen(records, RULES)
key = {
    "schema_version": "1.0",
    "note": "Expected decisions derived from the SAME rules; rules are the fixture source of truth.",
    "expected_counts": result["counts"],
    "expected_decisions": {d["record_id"]: d["decision"] for d in result["decisions"]},
}
(OUT / "screening-expected-key.json").write_text(
    json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(json.dumps({"records": len(records), "counts": result["counts"]}, indent=2))
