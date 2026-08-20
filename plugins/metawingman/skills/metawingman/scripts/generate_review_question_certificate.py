"""Generate an auditable Review Question Certificate (RQC) for a candidate
systematic-review topic.

The certificate separates universal review-quality requirements from an
optional hypothesis-testing mode. Estimation, mapping, and interpretive reviews
must be answerable and auditable, but are not forced into directional
falsification language.

Usage:
  python metawingman/scripts/generate_review_question_certificate.py \
    --topic "topic text" \
    --provider-config metawingman/references/deepseek-provider-config.json \
    --out cert.json [--no-novelty-search]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metawingman_core.deepseek_provider import DeepSeekProvider
from metawingman_core.model_provider import ModelProvider, ProviderResult
from metawingman_core.openai_compatible_provider import OpenAICompatibleProvider
from metawingman_core.schema_guard import SchemaValidationError, validate_document

SCHEMA = "review_question_certificate"
HARD_GATE_MIN_SCORE = 3
QUALITY_DIMENSIONS = (
    "clinical_relevance",
    "method_fit",
    "traceability",
    "explainability",
    "reproducibility",
)
CLAIM_MODES = {"hypothesis_test", "estimation", "mapping", "interpretive_synthesis"}
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


@dataclass(frozen=True)
class GateResult:
    passed: bool
    hard_failures: list[str]
    soft_repairs: list[str]


def hard_gate(certificate: dict[str, Any]) -> GateResult:
    """Deterministic hard/soft gate over a completed certificate (pure)."""
    hard: list[str] = []
    soft: list[str] = []
    hypothesis = certificate["hypothesis"]
    claim_mode = hypothesis.get("claim_mode")
    if claim_mode not in CLAIM_MODES:
        hard.append("claim_mode_invalid")
    if not hypothesis.get("answerability_criterion", "").strip():
        hard.append("answerability_criterion_empty")
    if claim_mode == "hypothesis_test" and not hypothesis.get("falsifiable_statement", "").strip():
        hard.append("falsifiable_statement_empty")
    if not certificate["mechanism_model"]["summary"].strip():
        hard.append("mechanism_summary_empty")
    if claim_mode == "hypothesis_test" and not certificate["minimal_decisive_test"]["rejection_observation"].strip():
        hard.append("rejection_observation_empty")
    scores = certificate["quality_scores"]
    for dimension in QUALITY_DIMENSIONS:
        if scores[dimension] < HARD_GATE_MIN_SCORE:
            soft.append(f"{dimension}_model_score_low_requires_external_verification")
    if certificate["novelty_gate"]["verdict"] == "covered":
        hard.append("novelty_verdict_covered")
    if certificate["novelty_gate"]["verdict"] == "incremental":
        soft.append("novelty_incremental_consider_living_update")
    if not any(a["justification"].strip() for a in certificate["first_principle_assumptions"]):
        hard.append("assumptions_unjustified")
    return GateResult(passed=not hard, hard_failures=hard, soft_repairs=soft)


def _prompt(stage: str, topic: str, prior: dict[str, Any] | None) -> str:
    prior_text = json.dumps(prior, ensure_ascii=False, indent=2) if prior else "(none)"
    stage_specs = {
        "primitives": "Output ONLY JSON: population/intervention/comparator as strings; outcomes as a list of {name, level in [patient_important, surrogate], timepoint}; study_designs as a list. No prose.",
        "assumptions": "Output ONLY JSON: first_principle_assumptions as a list of {statement, justification}. No prose.",
        "mechanism": "Output ONLY JSON: {exposure, outcome, pathway_nodes: [..], moderators: [..], summary: one-sentence mechanism summary}. No prose.",
        "tension": "Output ONLY JSON: {type in [guideline_discord, direction_inconsistency, heterogeneity, outdated_evidence, evidence_gap], description, evidence_sources: [{url_or_doi, fetched: false}]}. No prose.",
        "question_hypothesis": "Output ONLY JSON: {research_question: structured clinical review question, hypothesis: {claim_mode: one of [hypothesis_test, estimation, mapping, interpretive_synthesis], direction, magnitude, falsifiable_statement, answerability_criterion, heterogeneity_pattern}}. Use falsifiable_statement only for hypothesis_test; otherwise return an empty string. No prose.",
        "test_update": "Output ONLY JSON: {minimal_decisive_test: {description, rejection_observation, evidence_required: [..]}, expected_observations: [..], failure_update_rule: {negative_result_action in [downgrade_narrative, subgroup_refocus, terminate], description}}. No prose.",
        "scores": "Output ONLY JSON: {clinical_relevance, method_fit, traceability, explainability, reproducibility} each integer 0-5. Judge professional review quality; do not use falsifiability as a universal quality proxy. No prose.",
    }
    return (
        "You are a systematic-review methodologist producing one auditable part of a "
        "Review Question Certificate for a clinical evidence-synthesis topic.\n"
        f"TOPIC: {topic}\n"
        f"PRIOR DERIVATION (JSON): {prior_text}\n"
        f"STAGE: {stage}\n"
        f"{stage_specs[stage]}"
    )


def _parse_json(result: ProviderResult) -> dict[str, Any]:
    text = result.content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"provider returned no JSON object for stage: {text[:120]}")
    return json.loads(text[start : end + 1])


def fetch_existing_reviews_europepmc(topic: str, timeout_seconds: float = 20.0) -> list[dict[str, str]]:
    """Novelty evidence: recent reviews from Europe PMC for the topic terms."""
    query = urllib.parse.quote(f'({topic}) AND (PUB_TYPE:"Review") AND (SRC:MED)')
    url = f"{EUROPEPMC_SEARCH}?query={query}&format=json&pageSize=10&resultType=lite&sort=P_PDATE_D%20desc"
    request = urllib.request.Request(url, headers={"User-Agent": "MetaWingman-RQC/1.0"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    reviews = []
    for item in payload.get("resultList", {}).get("result", []):
        reviews.append({
            "title": item.get("title", ""),
            "source": "europepmc",
            "identifier": item.get("id", ""),
        })
    return reviews


def generate_certificate(
    topic: str,
    provider: ModelProvider,
    fetch_reviews: Callable[[str], list[dict[str, str]]],
    *,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Run the typed derivation pipeline and return a full RQC."""
    prompts_sha: dict[str, str] = {}
    contents_sha: list[str] = []
    prior: dict[str, Any] | None = None
    assembled: dict[str, Any] = {}

    for stage in ("primitives", "assumptions", "mechanism", "tension", "question_hypothesis", "test_update", "scores"):
        prompt = _prompt(stage, topic, prior)
        prompts_sha[stage] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        result = provider.chat(
            [{"role": "user", "content": prompt}],
            max_tokens=8192,
            json_output=False,
            thinking=False,
        )
        contents_sha.append(result.content_sha256)
        stage_out = _parse_json(result)
        if stage == "primitives":
            assembled["primitives"] = stage_out
        elif stage == "assumptions":
            assembled["first_principle_assumptions"] = stage_out["first_principle_assumptions"]
        elif stage == "mechanism":
            assembled["mechanism_model"] = stage_out
        elif stage == "tension":
            assembled["tension"] = stage_out
        elif stage == "question_hypothesis":
            assembled["research_question"] = stage_out["research_question"]
            assembled["hypothesis"] = stage_out["hypothesis"]
        elif stage == "test_update":
            assembled["minimal_decisive_test"] = stage_out["minimal_decisive_test"]
            assembled["expected_observations"] = stage_out["expected_observations"]
            assembled["failure_update_rule"] = stage_out["failure_update_rule"]
        elif stage == "scores":
            scores = {key: int(stage_out[key]) for key in QUALITY_DIMENSIONS}
            scores["average"] = round(sum(scores.values()) / 5, 3)
            scores["provenance"] = "model_proposed_unvalidated"
            assembled["quality_scores"] = scores
        prior = stage_out

    existing = fetch_reviews(topic)
    covered = any(_title_overlap(topic, item["title"]) for item in existing)
    assembled["novelty_gate"] = {
        "existing_reviews": existing[:10],
        "gap_statement": f"Europe PMC 检索到 {len(existing)} 条近期待审综述；门控基于标题重叠启发式，最终以人工核对为准。",
        "verdict": "covered" if covered else "novel",
        "live_update_eligible": covered,
    }

    gate = hard_gate(assembled)
    assembled["gate"] = {
        "passed": gate.passed,
        "scope": "candidate_structure_only",
        "scientific_release_ready": False,
        "hard_failures": gate.hard_failures,
        "soft_repairs": gate.soft_repairs,
    }

    fingerprint = hashlib.sha256(
        json.dumps(assembled, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    certificate = {
        "schema_version": "1.1",
        "certificate_id": f"rqc:{fingerprint}",
        "created_at_utc": created_at_utc or datetime.now(timezone.utc).isoformat(),
        "topic": {
            "domain": topic.split(";")[0].strip() if topic else "",
            "working_title": topic,
            "candidate_question_text": topic,
        },
        **assembled,
        "audit": {
            "provider": provider.provider_name if hasattr(provider, "provider_name") else "injected",
            "model": provider.model if hasattr(provider, "model") else "injected",
            "prompt_sha256s": prompts_sha,
            "provider_content_sha256": hashlib.sha256("|".join(contents_sha).encode()).hexdigest(),
        },
    }
    validate_document(certificate, SCHEMA)
    return certificate


def _title_overlap(topic: str, title: str) -> bool:
    """Cheap overlap heuristic; final novelty judgment is human-reviewed."""
    terms = {word.lower() for word in topic.replace(";", " ").split() if len(word) > 3}
    title_terms = {word.lower() for word in title.split()}
    return bool(terms) and len(terms & title_terms) >= min(2, len(terms))


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
    parser.add_argument("--topic", required=True)
    parser.add_argument("--provider-config", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("review-question-certificate.json"))
    parser.add_argument("--no-novelty-search", action="store_true")
    args = parser.parse_args()
    try:
        provider = _load_provider(args.provider_config)
        fetch = (lambda _topic: []) if args.no_novelty_search else fetch_existing_reviews_europepmc
        certificate = generate_certificate(args.topic, provider, fetch)
        args.out.write_text(json.dumps(certificate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"certificate_id": certificate["certificate_id"], "gate_passed": certificate["gate"]["passed"], "out": str(args.out)}, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, SchemaValidationError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
