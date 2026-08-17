"""Compile model-proposed eligibility criteria into a typed protocol representation."""

from __future__ import annotations

import argparse
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema_guard import validate_document


ALLOWED_DOMAINS = {
    "population", "intervention", "exposure", "comparator", "outcome",
    "design", "setting", "timepoint", "report", "other",
}
ALLOWED_OPERATORS = {
    "equals", "not_equals", "in", "not_in", "contains", "exists",
    "gte", "gt", "lte", "lt", "between",
}
NUMERIC_OPERATORS = {"gte", "gt", "lte", "lt", "between"}


@dataclass(frozen=True)
class CompileIssue:
    criterion_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class CompileResult:
    document: dict[str, Any]
    issues: tuple[CompileIssue, ...]

    @property
    def ready_to_freeze(self) -> bool:
        return not self.issues and all(item["status"] == "operational" for item in self.document["criteria"])


@dataclass(frozen=True)
class ProtocolPlanIssue:
    path: str
    code: str
    detail: str


@dataclass(frozen=True)
class ProtocolPlanCompileResult:
    document: dict[str, Any]
    issues: tuple[ProtocolPlanIssue, ...]

    @property
    def ready_to_freeze(self) -> bool:
        return not self.issues


PLACEHOLDER_VALUES = {
    "", "tbd", "todo", "unknown", "unspecified", "not specified", "to be defined",
    "待定", "未知", "未指定", "待补充",
}
FRAMEWORK_DIMENSIONS = {
    "PICO": {"population", "intervention", "comparator", "outcome"},
    "PECO": {"population", "exposure", "comparator", "outcome"},
    "PCC": {"population", "concept", "context"},
}


def _is_placeholder(value: Any) -> bool:
    return not isinstance(value, str) or value.strip().casefold() in PLACEHOLDER_VALUES


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def inspect_protocol_plan(document: dict[str, Any]) -> list[ProtocolPlanIssue]:
    """Find operational ambiguity that JSON shape validation cannot detect."""

    issues: list[ProtocolPlanIssue] = []
    context = document["decision_context"]
    for key in ("decision", "setting", "intended_use"):
        if _is_placeholder(context[key]):
            issues.append(ProtocolPlanIssue(f"decision_context.{key}", "decision_context_not_operational", f"Define {key} explicitly."))
    if not context["stakeholders"]:
        issues.append(ProtocolPlanIssue("decision_context.stakeholders", "stakeholders_missing", "Name the intended decision stakeholders."))

    questions = document["review_questions"]
    question_ids = [item["question_id"] for item in questions]
    for duplicate in sorted(_duplicates(question_ids)):
        issues.append(ProtocolPlanIssue("review_questions", "duplicate_question_id", duplicate))
    for index, question in enumerate(questions):
        path = f"review_questions[{index}]"
        if _is_placeholder(question["objective"]):
            issues.append(ProtocolPlanIssue(f"{path}.objective", "objective_not_operational", "State an answerable objective."))
        names = [item["name"].strip().casefold() for item in question["dimensions"]]
        for duplicate in sorted(_duplicates(names)):
            issues.append(ProtocolPlanIssue(f"{path}.dimensions", "duplicate_dimension", duplicate))
        required = FRAMEWORK_DIMENSIONS.get(question["framework"], set())
        missing = sorted(required - set(names))
        if missing:
            issues.append(ProtocolPlanIssue(f"{path}.dimensions", "framework_dimension_missing", ", ".join(missing)))
        for dim_index, dimension in enumerate(question["dimensions"]):
            if _is_placeholder(dimension["value"]) or _is_placeholder(dimension["operational_definition"]):
                issues.append(ProtocolPlanIssue(
                    f"{path}.dimensions[{dim_index}]",
                    "dimension_not_operational",
                    f"Operationalize {dimension['name']} with a value and observable definition.",
                ))

    outcomes = document["outcome_hierarchy"]
    outcome_ids = [item["outcome_id"] for item in outcomes]
    for duplicate in sorted(_duplicates(outcome_ids)):
        issues.append(ProtocolPlanIssue("outcome_hierarchy", "duplicate_outcome_id", duplicate))
    outcome_by_id = {item["outcome_id"]: item for item in outcomes}
    for index, outcome in enumerate(outcomes):
        path = f"outcome_hierarchy[{index}]"
        if _is_placeholder(outcome["construct"]) or _is_placeholder(outcome["result_selection_rule"]):
            issues.append(ProtocolPlanIssue(path, "outcome_not_operational", "Define the construct and a deterministic result-selection rule."))

    syntheses = document["synthesis_questions"]
    synthesis_ids = [item["synthesis_id"] for item in syntheses]
    for duplicate in sorted(_duplicates(synthesis_ids)):
        issues.append(ProtocolPlanIssue("synthesis_questions", "duplicate_synthesis_id", duplicate))
    for index, synthesis in enumerate(syntheses):
        path = f"synthesis_questions[{index}]"
        unknown_questions = sorted(set(synthesis["review_question_ids"]) - set(question_ids))
        if unknown_questions:
            issues.append(ProtocolPlanIssue(f"{path}.review_question_ids", "unknown_review_question", ", ".join(unknown_questions)))
        outcome = outcome_by_id.get(synthesis["outcome_id"])
        if outcome is None:
            issues.append(ProtocolPlanIssue(f"{path}.outcome_id", "unknown_outcome", synthesis["outcome_id"]))
        else:
            if synthesis["effect_measure"] not in outcome["preferred_measures"]:
                issues.append(ProtocolPlanIssue(f"{path}.effect_measure", "effect_measure_outside_outcome_plan", synthesis["effect_measure"]))
            if synthesis["time_window"] not in outcome["time_windows"]:
                issues.append(ProtocolPlanIssue(f"{path}.time_window", "time_window_outside_outcome_plan", synthesis["time_window"]))
        for field in ("population", "contrast", "time_window", "effect_measure", "poolability_rule"):
            if _is_placeholder(synthesis[field]):
                issues.append(ProtocolPlanIssue(f"{path}.{field}", "synthesis_field_not_operational", f"Define {field}."))
        estimand = synthesis["estimand"]
        for field in ("target_population", "contrast", "outcome", "time_horizon", "population_summary", "analysis_unit"):
            if _is_placeholder(estimand[field]):
                issues.append(ProtocolPlanIssue(f"{path}.estimand.{field}", "estimand_field_not_operational", f"Define {field}."))
        threshold_ids = [item["threshold_id"] for item in synthesis["decision_thresholds"]]
        for duplicate in sorted(_duplicates(threshold_ids)):
            issues.append(ProtocolPlanIssue(f"{path}.decision_thresholds", "duplicate_threshold_id", duplicate))
        for threshold_index, threshold in enumerate(synthesis["decision_thresholds"]):
            if threshold["value"] == "" or _is_placeholder(threshold["rationale"]):
                issues.append(ProtocolPlanIssue(
                    f"{path}.decision_thresholds[{threshold_index}]",
                    "decision_threshold_not_operational",
                    "Set an explicit value and prospective rationale.",
                ))

    artifact = document["criteria_artifact"]
    if artifact["status"] == "draft" or artifact["sha256"] is None:
        issues.append(ProtocolPlanIssue("criteria_artifact", "criteria_not_frozen", "Freeze and hash the compiled eligibility criteria."))
    if not document["source_plan"]:
        issues.append(ProtocolPlanIssue("source_plan", "source_plan_missing", "Specify the databases, registries, and supplementary search routes."))
    for index, source in enumerate(document["source_plan"]):
        if source["required"] and (_is_placeholder(source["coverage"]) or not source["query_file"]):
            issues.append(ProtocolPlanIssue(
                f"source_plan[{index}]", "required_source_not_operational",
                "A required source needs coverage and a reconstructable query file.",
            ))
    return issues


def compile_full_protocol(candidate: dict[str, Any]) -> ProtocolPlanCompileResult:
    """Validate a typed full protocol and downgrade an ambiguous freeze request."""

    document = copy.deepcopy(candidate)
    document.setdefault("schema_version", "1.0")
    try:
        validate_document(document, "protocol")
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    issues = inspect_protocol_plan(document)
    if issues and document["status"] in {"frozen", "amended"}:
        document["status"] = "draft"
        document["frozen_at_utc"] = None
        document["frozen_by"] = None
        validate_document(document, "protocol")
    return ProtocolPlanCompileResult(document=document, issues=tuple(issues))


def _normalize_criterion(raw: dict[str, Any], position: int) -> tuple[dict[str, Any], list[CompileIssue]]:
    criterion_id = str(raw.get("criterion_id") or f"criterion-{position:03d}")
    issues: list[CompileIssue] = []
    domain = str(raw.get("domain") or "other")
    if domain not in ALLOWED_DOMAINS:
        issues.append(CompileIssue(criterion_id, "unknown_domain", f"Unsupported domain: {domain}"))
        domain = "other"

    predicate = raw.get("predicate") if isinstance(raw.get("predicate"), dict) else {}
    field = str(predicate.get("field") or raw.get("field") or "__unresolved__")
    operator = str(predicate.get("operator") or raw.get("operator") or "exists")
    value = predicate.get("value", raw.get("value"))
    unit = predicate.get("unit", raw.get("unit"))
    normalization = str(predicate.get("normalization") or raw.get("normalization") or "none")

    if field == "__unresolved__":
        issues.append(CompileIssue(criterion_id, "field_not_operationalized", "Map the criterion to an observable field."))
    if operator not in ALLOWED_OPERATORS:
        issues.append(CompileIssue(criterion_id, "unknown_operator", f"Unsupported operator: {operator}"))
        operator = "exists"
    if operator in {"in", "not_in"} and (not isinstance(value, list) or not value):
        issues.append(CompileIssue(criterion_id, "invalid_set_value", "Use a non-empty value list for set membership."))
    if operator == "between" and (not isinstance(value, list) or len(value) != 2):
        issues.append(CompileIssue(criterion_id, "invalid_range", "Use exactly two bounds for between."))
    if operator not in {"exists"} and value is None:
        issues.append(CompileIssue(criterion_id, "missing_predicate_value", "Provide an explicit comparison value."))
    if operator in NUMERIC_OPERATORS and not unit:
        issues.append(CompileIssue(criterion_id, "missing_unit", "Provide the unit for a numeric threshold."))

    missing_policy = str(raw.get("missing_policy") or "unclear")
    if missing_policy not in {"unclear", "not_reported", "exclude", "include"}:
        issues.append(CompileIssue(criterion_id, "invalid_missing_policy", f"Unsupported missing policy: {missing_policy}"))
        missing_policy = "unclear"

    criterion = {
        "criterion_id": criterion_id,
        "domain": domain,
        "label": str(raw.get("label") or criterion_id),
        "predicate": {
            "field": field,
            "operator": operator,
            "value": value,
            "unit": unit,
            "normalization": normalization,
        },
        "missing_policy": missing_policy,
        "full_text_required": bool(raw.get("full_text_required", False)),
        "status": "needs_human_definition" if issues else "operational",
        "source_section": str(raw.get("source_section") or "Eligibility criteria"),
    }
    return criterion, issues


def compile_protocol(candidate: dict[str, Any]) -> CompileResult:
    raw_criteria = candidate.get("criteria")
    if not isinstance(raw_criteria, list):
        raise ValueError("candidate.criteria must be a list")
    criteria: list[dict[str, Any]] = []
    issues: list[CompileIssue] = []
    seen_ids: set[str] = set()
    for position, raw in enumerate(raw_criteria, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"candidate.criteria[{position - 1}] must be an object")
        criterion, criterion_issues = _normalize_criterion(raw, position)
        if criterion["criterion_id"] in seen_ids:
            criterion_issues.append(CompileIssue(criterion["criterion_id"], "duplicate_criterion_id", "Criterion IDs must be unique."))
            criterion["status"] = "needs_human_definition"
        seen_ids.add(criterion["criterion_id"])
        criteria.append(criterion)
        issues.extend(criterion_issues)

    requested_status = str(candidate.get("status") or "draft")
    if requested_status not in {"draft", "frozen", "amended"}:
        raise ValueError(f"Unsupported protocol status: {requested_status}")
    document = {
        "schema_version": "1.0",
        "protocol_version": str(candidate.get("protocol_version") or "0.1-draft"),
        "status": "draft" if issues and requested_status == "frozen" else requested_status,
        "criteria": criteria,
    }
    validate_document(document, "protocol_criteria")
    return CompileResult(document=document, issues=tuple(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="Model-proposed structured protocol JSON")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--kind", choices=("criteria", "full"), default="criteria")
    args = parser.parse_args()
    try:
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        result = compile_protocol(candidate) if args.kind == "criteria" else compile_full_protocol(candidate)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"compiled": False, "error": str(exc)}, indent=2))
        return 1
    payload = {
        "compiled": True,
        "ready_to_freeze": result.ready_to_freeze,
        "issues": [issue.__dict__ for issue in result.issues],
        "document": result.document,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result.document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if result.ready_to_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
