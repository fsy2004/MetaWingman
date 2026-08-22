"""Hard gates for representative, authoritative direct-evidence cases."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from .schema_guard import validate_document


class CaseAdmissionError(ValueError):
    pass


def _normalized_doi(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    return text.rstrip(". ")


def _normalized_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def _load_training_identities(
    registry: dict[str, Any], repository_root: Path,
) -> tuple[set[str], set[str]]:
    dois: set[str] = set()
    titles: set[str] = set()
    for binding in registry["training_corpus_bindings"]:
        path = (repository_root / binding["path"]).resolve()
        try:
            path.relative_to(repository_root)
        except ValueError as exc:
            raise CaseAdmissionError("training corpus binding path escapes repository") from exc
        if not path.is_file():
            raise CaseAdmissionError("training corpus binding is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
            raise CaseAdmissionError("training corpus binding hash mismatch")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CaseAdmissionError("training corpus binding is not valid JSON") from exc
        for record in document.get("records", []):
            doi = _normalized_doi(record.get("doi"))
            title = _normalized_title(record.get("title"))
            if doi:
                dois.add(doi)
            if title:
                titles.add(title)
    return dois, titles


def _verify_material_snapshot_receipt(case: dict[str, Any]) -> None:
    binding = case.get("material_snapshot_receipt")
    if binding is None:
        return
    repository_root = Path(__file__).resolve().parents[3]
    path = (repository_root / binding["path"]).resolve()
    try:
        path.relative_to(repository_root)
    except ValueError as exc:
        raise CaseAdmissionError(
            f"{case['case_id']}: material snapshot receipt path escapes repository"
        ) from exc
    if not path.is_file():
        raise CaseAdmissionError(
            f"{case['case_id']}: material snapshot receipt is missing"
        )
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if observed != binding["sha256"]:
        raise CaseAdmissionError(
            f"{case['case_id']}: material snapshot receipt hash mismatch"
        )


def _scale_passes(case: dict[str, Any]) -> bool:
    scale = case["evidence_scale"]
    route = scale["route"]
    studies = int(scale.get("studies") or 0)
    participants = int(scale.get("participants") or 0)
    countries = int(scale.get("countries") or 0)
    records = int(scale.get("records") or 0)
    diagnostic_tests = int(scale.get("diagnostic_tests") or 0)
    if route == "network_or_living_nma":
        return studies >= 30 or participants >= 10_000
    if route == "broad_intervention_meta_analysis":
        return studies >= 30 or participants >= 5_000
    if route == "broad_public_health_exposure":
        return studies >= 100 or countries >= 20 or participants >= 50_000
    if route == "diagnostic_accuracy_review":
        return studies >= 30 or diagnostic_tests >= 10_000
    if route == "prognosis_or_prediction_review":
        return studies >= 30 or participants >= 5_000
    if route == "prevalence_incidence_review":
        return studies >= 30 or participants >= 10_000
    if route == "structured_narrative_review":
        return studies >= 20 or records >= 20 or countries >= 5
    return False


def validate_case_registry(registry: dict[str, Any]) -> dict[str, int]:
    """Validate schema plus scientific admission gates; authority never affects scores."""
    policy = registry.get("selection_policy", {})
    if not policy.get("authority_is_admission_only") or not policy.get("authority_is_never_a_score_feature"):
        raise CaseAdmissionError("authority or journal prestige cannot be a score feature")
    try:
        validate_document(registry, "direct_evidence_case_registry")
    except Exception as exc:
        raise CaseAdmissionError(str(exc)) from exc
    repository_root = Path(__file__).resolve().parents[3]
    training_dois, training_titles = _load_training_identities(registry, repository_root)
    held_out_overlaps: list[str] = []
    family_splits: dict[str, set[str]] = {}
    represented_profile_strata: set[str] = set()
    ready = 0
    for case in registry["cases"]:
        _verify_material_snapshot_receipt(case)
        split = case["split"]
        represented_profile_strata.update(case["profile_strata"])
        family_splits.setdefault(case["review_family_id"], set()).add(split)
        if split == "held_out" and case["training_use"] != "forbidden":
            raise CaseAdmissionError(f"{case['case_id']}: held-out case is forbidden from training")
        if split == "held_out" and (
            _normalized_doi(case["doi"]) in training_dois
            or _normalized_title(case["title"]) in training_titles
        ):
            held_out_overlaps.append(case["case_id"])
            raise CaseAdmissionError(
                f"{case['case_id']}: held-out identity overlaps training corpus"
            )
        if split == "diagnostic_only" and case["training_use"] not in {"audit_only", "forbidden"}:
            raise CaseAdmissionError(f"{case['case_id']}: diagnostic-only case cannot provide training examples")
        if split in {"development", "held_out"}:
            if not case["authority"]["primary_identity_verified"]:
                raise CaseAdmissionError(f"{case['case_id']}: primary authority identity is not verified")
            if not case["decision_relevance"]["broad_population_or_system_relevance"]:
                raise CaseAdmissionError(f"{case['case_id']}: broad decision relevance is required")
            if not _scale_passes(case):
                raise CaseAdmissionError(f"{case['case_id']}: representativeness floor not met")
        if case["execution_status"] == "run_ready":
            if not case["historical_cutoff"]["exact"]:
                raise CaseAdmissionError(f"{case['case_id']}: exact historical cutoff required")
            materials = case["operational_materials"]
            if not all(materials[field] == "verified" for field in (
                "search_strategy", "search_export", "screening_reference",
                "extraction_reference", "lawful_source_route",
            )):
                raise CaseAdmissionError(f"{case['case_id']}: complete operational materials required")
            if "living_review" in case["profile_strata"]:
                graph = case.get("reference_version_graph")
                if not graph or graph["binding_status"] != "resolved":
                    raise CaseAdmissionError(f"{case['case_id']}: run-ready living case requires a resolved reference version graph")
            ready += 1

        graph = case.get("reference_version_graph")
        if graph:
            version_ids = {item["version_id"] for item in graph["versions"]}
            if graph["target_version_id"] not in version_ids:
                raise CaseAdmissionError(f"{case['case_id']}: target reference version is absent from version graph")
            target = [item for item in graph["versions"] if item["version_id"] == graph["target_version_id"]]
            if len(target) != 1 or target[0]["role"] != "target":
                raise CaseAdmissionError(f"{case['case_id']}: version graph must identify exactly one target")

    for family, splits in family_splits.items():
        if "development" in splits and "held_out" in splits:
            raise CaseAdmissionError(f"review family {family} crosses development and held-out splits")
    required_profile_strata = set(registry["required_profile_strata"])
    return {
        "development_candidates": sum(case["split"] == "development" for case in registry["cases"]),
        "held_out_candidates": sum(case["split"] == "held_out" for case in registry["cases"]),
        "training_corpus_binding_verified": True,
        "held_out_training_identity_overlaps": held_out_overlaps,
        "locked_execution_ready": ready,
        "represented_profile_strata": sorted(represented_profile_strata),
        "missing_profile_strata": sorted(required_profile_strata - represented_profile_strata),
    }
