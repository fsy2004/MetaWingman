"""Double-judge blind scoring for Review Question Certificates.

Generator metadata and self-scores are stripped so judges see only certificate
content. Independent judges score five professional evidence-synthesis quality
dimensions, then the script reports averages, ranking, and agreement.

Usage:
  python metawingman/scripts/blind_judge_certificates.py \
    --certs cert1.json cert2.json \
    --judge-a-config metawingman/references/deepseek-provider-config.json \
    --judge-b-config metawingman/references/glm-provider-config.json \
    --out judge-report.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metawingman_core.deepseek_provider import DeepSeekProvider
from metawingman_core.model_provider import ModelProvider, ProviderResult
from metawingman_core.openai_compatible_provider import OpenAICompatibleProvider

DIMENSIONS = (
    "clinical_relevance",
    "method_fit",
    "traceability",
    "explainability",
    "reproducibility",
)

JUDGE_PROMPT = """You are an independent scientific reviewer scoring a research-question certificate for a clinical evidence-synthesis topic. Score each dimension 1 (poor) to 5 (excellent):
- clinical_relevance: would answering the question inform a real clinical or research decision?
- method_fit: does the proposed review and synthesis method fit the question, estimand, and evidence?
- traceability: are claims and decisions anchored to identifiable sources?
- explainability: can a reviewer inspect why the scope and method were chosen?
- reproducibility: are the planned inputs, rules, and analysis sufficiently specified to rerun?
Falsifiability is required only when claim_mode is hypothesis_test. Do not penalize estimation, mapping, or interpretive synthesis for lacking a directional hypothesis.
Output ONLY JSON: {"scores": {"clinical_relevance": int, "method_fit": int, "traceability": int, "explainability": int, "reproducibility": int}, "overall": int, "rationale": "one sentence"}.

CERTIFICATE:
"""


def blind_certificate(certificate: dict[str, Any]) -> dict[str, Any]:
    """Strip generator metadata, self-scores, and gate verdicts so judges
    are not anchored by them."""
    stripped = dict(certificate)
    for key in ("audit", "quality_scores", "gate", "certificate_id", "created_at_utc", "schema_version"):
        stripped.pop(key, None)
    return stripped


def judge_scores(provider: ModelProvider, certificate: dict[str, Any]) -> dict[str, Any]:
    blinded = blind_certificate(certificate)
    prompt = JUDGE_PROMPT + json.dumps(blinded, ensure_ascii=False, indent=2)
    result = provider.chat(
        [{"role": "user", "content": prompt}],
        max_tokens=8192, json_output=False, thinking=False,
    )
    text = result.content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"judge returned no JSON: {text[:120]}")
    parsed = json.loads(text[start : end + 1])
    scores = {key: int(parsed["scores"][key]) for key in DIMENSIONS}
    return {"scores": scores, "overall": int(parsed.get("overall", 0)), "rationale": parsed.get("rationale", "")}


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return 0.0
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def build_report(
    cert_ids: Sequence[str],
    judge_a: Sequence[dict[str, Any]],
    judge_b: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    for cert_id, a, b in zip(cert_ids, judge_a, judge_b):
        avg_a = sum(a["scores"].values()) / len(DIMENSIONS)
        avg_b = sum(b["scores"].values()) / len(DIMENSIONS)
        rows.append({
            "certificate_id": cert_id,
            "judge_a": a, "judge_b": b,
            "average_a": round(avg_a, 3), "average_b": round(avg_b, 3),
            "average": round((avg_a + avg_b) / 2, 3),
        })
    rows.sort(key=lambda row: row["average"], reverse=True)
    agreement = _pearson(
        [row["average_a"] for row in rows], [row["average_b"] for row in rows]
    )
    return {
        "schema_version": "1.0",
        "rows": rows,
        "ranking": [row["certificate_id"] for row in rows],
        "inter_judge_pearson": round(agreement, 3),
        "judge_count": 2,
        "dimensions": list(DIMENSIONS),
        "interpretation": "diagnostic_only_not_ground_truth",
    }


def _load_provider(config_path: Path) -> ModelProvider:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    adapter = config.get("adapter", "openai_compatible")
    if adapter == "deepseek":
        return DeepSeekProvider(base_url=config.get("base_url"), model=config.get("model"))
    return OpenAICompatibleProvider(
        provider_name=config.get("provider_id", "configured"),
        base_url=config["base_url"],
        model=config["model"],
        api_key_required=config.get("api_key_required", True),
        api_key_env=config.get("api_key_env", "MODEL_API_KEY"),
        credential_target=config.get("credential_target"),
        allow_local_http=config.get("allow_local_http", False),
        supports_json_output=config.get("features", {}).get("json_output", True),
        supports_reasoning_effort=config.get("features", {}).get("reasoning_effort", False),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certs", nargs="+", type=Path, required=True)
    parser.add_argument("--judge-a-config", type=Path, required=True)
    parser.add_argument("--judge-b-config", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("judge-report.json"))
    args = parser.parse_args()
    try:
        certs = [json.loads(path.read_text(encoding="utf-8")) for path in args.certs]
        cert_ids = [cert.get("certificate_id") or str(path) for cert, path in zip(certs, args.certs)]
        provider_a = _load_provider(args.judge_a_config)
        provider_b = _load_provider(args.judge_b_config)
        judge_a = [judge_scores(provider_a, cert) for cert in certs]
        judge_b = [judge_scores(provider_b, cert) for cert in certs]
        report = build_report(cert_ids, judge_a, judge_b)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
