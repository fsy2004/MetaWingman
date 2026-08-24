#!/usr/bin/env python3
"""Build a real evidence landscape and the design-signal dict a design decision needs.

This is the "real landscape builder" path: from family-tagged records (records
collected from a top-journal corpus or a PubMed non-target pool) aggregate the
evidence-structure signals that derive_review_design consumes. It wraps
build_evidence_landscape but adds two things the core landscape cannot infer on
its own:

  * exposure_outcome_design — the core summary guesses 'rct' unless a family is a
    reference-standard or prediction-model family. Real exposure-outcome reviews
    are almost always observational; a record may carry this explicitly.
  * question_shape injection — the clinical/methodological shape (which profile
    family the question belongs to) is a question property, not a landscape one.

The builder never scores topics by prestige, citation count, or fluency; it only
aggregates structure.
"""

from __future__ import annotations

from typing import Any

from metawingman.scripts.metawingman_core.evidence_landscape import build_evidence_landscape
from metawingman.benchmark.gold_loader import GoldCase


def signal_from_records(
    question: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    family_id: str | None = None,
    family_field: str = "review_family_id",
) -> dict[str, Any]:
    """Build the design-signal dict for one case from its raw (family-tagged) records.

    If records are empty, falls back to a structure-only signal derived from the
    question shape so the builder is usable on a case with only a clinical
    question (e.g. a prospective/empty corpus).
    """
    if not records:
        return _signal_from_question(question)

    fam = family_id or str(records[0].get(family_field) or "unbound")
    landscape = build_evidence_landscape(records, family_field=family_field)
    signal = landscape.summary(fam)

    # Core summary cannot infer exposure-outcome design; let a record-driven
    # override win when present, otherwise fall back to question shape.
    exp_design = _records_exposure_design(records, family_field=family_field)
    if exp_design:
        signal["exposure_outcome_design"] = exp_design
    elif question.get("is_public_health_exposure") or "exposure" in str(question.get("type", "")):
        signal["exposure_outcome_design"] = signal.get("exposure_outcome_design") or "observational"

    return signal


def _records_exposure_design(records: list[dict[str, Any]], family_field: str) -> str | None:
    for record in records:
        if record.get("exposure_outcome_design"):
            return str(record["exposure_outcome_design"]).lower()
    return None


def _signal_from_question(question: dict[str, Any]) -> dict[str, Any]:
    """A fallback signal built purely from question shape (prospective/empty corpus)."""
    qtype = str(question.get("type", "")).lower()
    unit = question.get("outcome_unit")
    signal: dict[str, Any] = {"n_nodes_assessed": True}
    if unit:
        signal["outcome_unit"] = str(unit)
    if "diagnos" in qtype or question.get("has_index_test_reference"):
        signal["has_reference_standard"] = True
    if question.get("has_prediction_model"):
        signal["has_prediction_model"] = True
    if question.get("is_living_or_update"):
        signal["is_update"] = True
    if "prevalence" in qtype or "incidence" in qtype or "proportion" in qtype:
        signal["outcome_unit"] = signal.get("outcome_unit") or "proportion"
    if "exposure" in qtype or question.get("is_public_health_exposure"):
        signal["exposure_outcome_design"] = "observational"
    if question.get("intervention_count"):
        signal["comparator_count"] = int(question["intervention_count"])
        signal["arms_per_study"] = int(question["intervention_count"])
    return signal


def records_from_corpus(
    corpus_records: list[dict[str, Any]],
    *,
    family_field: str = "review_family_id",
    intervention_field: str = "intervention_count",
    comparator_field: str = "comparator_count",
    reference_field: str = "has_reference_standard",
    prediction_field: str = "has_prediction_model",
    outcome_field: str = "outcome_unit",
    update_field: str = "is_update",
    exposure_design_field: str = "exposure_outcome_design",
) -> list[dict[str, Any]]:
    """Normalise raw corpus/report records into family-tagged landscape records.

    This is a thin, explicit mapping layer: it takes whatever field names a real
    extraction pipeline produces and normalises them to the names build_evidence_landscape
    expects. Missing fields are left out (so the landscape treats them as absent).
    A record with no family id is bound to 'unbound'.
    """
    out: list[dict[str, Any]] = []
    for rec in corpus_records:
        row: dict[str, Any] = {family_field: str(rec.get(family_field) or "unbound")}
        for src_field, dst_key in (
            (intervention_field, "intervention_count"),
            (comparator_field, "comparator_count"),
            (reference_field, "has_reference_standard"),
            (prediction_field, "has_prediction_model"),
            (outcome_field, "outcome_unit"),
            (update_field, "is_update"),
            (exposure_design_field, "exposure_outcome_design"),
        ):
            if rec.get(src_field) is not None:
                row[dst_key] = rec[src_field]
        if rec.get("node_coverage_checked"):
            row["node_coverage_checked"] = True
        out.append(row)
    return out


def build_gold_signals(
    gold: list[GoldCase],
    records_by_family: dict[str, list[dict[str, Any]]] | None = None,
    *,
    family_field: str = "review_family_id",
) -> dict[str, dict[str, Any]]:
    """Build a design-signal dict for each gold case.

    When records_by_family is given (the real landscape path), the signal comes
    from aggregated records. Otherwise it falls back to the gold case's own
    landscape field (the curated-signal path).
    """
    records_by_family = records_by_family or {}
    result: dict[str, dict[str, Any]] = {}
    for case in gold:
        recs = records_by_family.get(case.case_id)
        if recs:
            result[case.case_id] = signal_from_records(
                case.question, recs, family_id=case.case_id, family_field=family_field)
        else:
            result[case.case_id] = case.landscape or _signal_from_question(case.question)
    return result
