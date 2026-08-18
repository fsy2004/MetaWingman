"""Generate the deterministic extraction acceptance fixture (v2 stage 2).

6 included records with known field values; one record deliberately misses
the field (expected status missing). Writes records JSONL + extraction
template + an expected key derived from the SAME template (the template is
the fixture's source of truth).
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

template = {
    "schema_version": "1.0",
    "stage": "extraction",
    "source_note": "Synthetic acceptance fixture (reconstruction-runner-v2-preregistration).",
    "fields": {
        "n_intervention": {
            "id": "ext-n-int",
            "pattern": r"intervention[^0-9]{0,40}(?P<value>\d{1,5})",
            "type": "int",
        },
        "n_control": {
            "id": "ext-n-ctrl",
            "pattern": r"control[^0-9]{0,40}(?P<value>\d{1,5})",
            "type": "int",
        },
        "sensitivity_percent": {
            "id": "ext-sens",
            "pattern": r"sensitivity[^0-9]{0,20}(?P<value>\d{1,3}(?:\.\d+)?)",
            "type": "float",
        },
    },
}

records = [
    {"id": "ext-01", "title": "Accuracy study A", "fulltext": "We enrolled intervention 232 and control 201 participants; sensitivity 78.5 percent."},
    {"id": "ext-02", "title": "Accuracy study B", "fulltext": "The intervention arm had 120 participants, control arm 118; sensitivity 81.0."},
    {"id": "ext-03", "title": "Accuracy study C", "fulltext": "Sensitivity was 69.3; intervention n=340, control n=352."},
    {"id": "ext-04", "title": "Accuracy study D", "fulltext": "Control arm: 90; intervention arm: 88; sensitivity 74."},
    {"id": "ext-05", "title": "Accuracy study E", "fulltext": "intervention 44, control 41 participants; sensitivity 90.1 percent."},
    {"id": "ext-06", "title": "Accuracy study F (missing counts)", "fulltext": "Sensitivity was 66.6 percent; sample sizes were not reported per arm."},
]
records_path = OUT / "extraction-records.jsonl"
records_path.write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
)
(OUT / "extraction-template.json").write_text(
    json.dumps(template, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)

import importlib.util
spec = importlib.util.spec_from_file_location(
    "run_extraction_slice",
    Path(__file__).resolve().parents[3] / "metawingman" / "scripts" / "run_extraction_slice.py",
)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
result = engine.extract(records, template)
key = {
    "schema_version": "1.0",
    "note": "Expected fields derived from the SAME template; template is the fixture source of truth.",
    "expected_coverage": result["coverage"],
    "expected_fields": {
        r["record_id"]: {name: f["status"] for name, f in r["fields"].items()} for r in result["rows"]
    },
}
(OUT / "extraction-expected-key.json").write_text(
    json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(json.dumps({"records": len(records), "coverage": result["coverage"]}, indent=2))
