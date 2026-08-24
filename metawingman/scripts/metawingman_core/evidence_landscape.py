#!/usr/bin/env python3
"""Build a cutoff-bounded evidence landscape and its design-relevant signal summary.

The landscape aggregates records/reports (from a family-isolated corpus) into the
evidence-structure signals the design-selection skill consumes: intervention-node
count, comparison-graph degree, presence of a reference standard, prediction-model
count, outcome unit, update flag, and node-coverage checks. It is deterministic and
does not score topics by prestige, citation count, or fluency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceLandscape:
    """A cutoff-bounded evidence landscape with design-relevant signals."""

    records: int
    families: int
    cutoffs: dict[str, str]           # family_id -> cutoff date (ISO or 'unresolved')
    comparator_nodes: dict[str, int]  # family_id -> distinct intervention/comparator nodes
    reference_standard_families: set[str]
    prediction_model_families: set[str]
    outcome_units: dict[str, str]     # family_id -> 'rate'|'proportion'|'continuous'|'binary'
    update_families: set[str]
    node_coverage: dict[str, bool]    # family_id -> record/report node coverage checked
    record_by_family: dict[str, int]  # family_id -> record count
    _source_hashes: dict[str, str] = field(default_factory=dict)

    def summary(self, family_id: str) -> dict[str, Any]:
        """Produce the signal dict consumed by derive_review_design."""
        return {
            "arms_per_study": self.comparator_nodes.get(family_id),
            "comparator_count": self.comparator_nodes.get(family_id),
            "has_reference_standard": family_id in self.reference_standard_families,
            "has_prediction_model": family_id in self.prediction_model_families,
            "outcome_unit": self.outcome_units.get(family_id),
            "exposure_outcome_design": self._design_guess(family_id),
            "is_update": family_id in self.update_families,
            "n_nodes_assessed": self.node_coverage.get(family_id, False),
            "has_geographic_dose_heterogeneity": bool(
                self.records and self.families and family_id in self.record_by_family
                and self.record_by_family[family_id] > 30
            ),
        }

    def _design_guess(self, family_id: str) -> str:
        if family_id in self.reference_standard_families:
            return "both"
        if family_id in self.prediction_model_families:
            return "observational"
        return "rct"


def build_evidence_landscape(
    records: list[dict[str, Any]],
    *,
    family_field: str = "review_family_id",
    cutoff_field: str = "historical_cutoff",
    intervention_field: str = "intervention_count",
    comparator_field: str = "comparator_count",
    reference_field: str = "has_reference_standard",
    prediction_field: str = "has_prediction_model",
    outcome_field: str = "outcome_unit",
    update_field: str = "is_update",
) -> EvidenceLandscape:
    """Aggregate record rows into a landscape. Records must be family-tagged."""
    if not records:
        raise ValueError("evidence landscape requires at least one record")
    families: set[str] = set()
    comparator_nodes: dict[str, int] = {}
    reference_std: set[str] = set()
    prediction_models: set[str] = set()
    outcome_units: dict[str, str] = {}
    updates: set[str] = set()
    node_cov: dict[str, bool] = {}
    cutoffs: dict[str, str] = {}
    record_by_family: dict[str, int] = {}

    for record in records:
        fam = str(record.get(family_field) or "unbound")
        families.add(fam)
        record_by_family[fam] = record_by_family.get(fam, 0) + 1
        if cutoff_field in record and record.get(cutoff_field):
            cutoffs[fam] = str(record[cutoff_field])
        nodes = max(record.get(intervention_field) or 0, record.get(comparator_field) or 0)
        if nodes:
            comparator_nodes[fam] = max(comparator_nodes.get(fam, 0), nodes)
        if record.get(reference_field):
            reference_std.add(fam)
        if record.get(prediction_field):
            prediction_models.add(fam)
        unit = record.get(outcome_field)
        if unit:
            outcome_units[fam] = str(unit)
        if record.get(update_field):
            updates.add(fam)
        # node coverage: a family with records has record-node coverage; report/study
        # coverage is a downstream check, but we record whether any node marks are present.
        node_cov[fam] = node_cov.get(fam, False) or bool(record.get("node_coverage_checked"))

    return EvidenceLandscape(
        records=len(records),
        families=len(families),
        cutoffs=cutoffs,
        comparator_nodes=comparator_nodes,
        reference_standard_families=reference_std,
        prediction_model_families=prediction_models,
        outcome_units=outcome_units,
        update_families=updates,
        node_coverage=node_cov,
        record_by_family=record_by_family,
    )
