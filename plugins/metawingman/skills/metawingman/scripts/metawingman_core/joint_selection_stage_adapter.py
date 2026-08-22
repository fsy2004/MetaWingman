"""Run complete, source-anchored title/abstract selection over every retrieved record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError, MeteredModelProvider
from .provider_factory import build_provider
from .schema_guard import SchemaValidationError, validate_document
from .screening_engine import ScreeningError, screen_record
from .state_store import atomic_write_json


ProviderBuilder = Callable[[dict[str, Any]], Any]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(root: Path, binding: dict[str, Any], label: str) -> Path:
    raw = Path(str(binding.get("path") or ""))
    path = raw.resolve(strict=False) if raw.is_absolute() else (root / raw).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise JointLifecycleRunError(f"{label} is outside the repository") from exc
    if not path.is_file() or _sha(path) != binding.get("sha256"):
        raise JointLifecycleRunError(f"{label} is missing or has hash drift")
    return path


def _prior_search_state(request: dict[str, Any], root: Path) -> tuple[dict[str, Any], Path]:
    path = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(path) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("search output manifest hash drift")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        stage = manifest["stage_output"]
        rows = [item for item in stage["artifacts"] if item["artifact_id"] == stage["state_artifact_id"]]
        if len(rows) != 1:
            raise KeyError("search state artifact")
        state_path = Path(rows[0]["path"]).resolve(strict=True)
        if _sha(state_path) != rows[0]["sha256"]:
            raise JointLifecycleRunError("search state artifact hash drift")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_document(state, "joint_search_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid search stage state: {exc}") from exc
    return state, state_path


def _contradiction(predicate: dict[str, Any]) -> Any:
    operator = predicate["operator"]
    expected = predicate["value"]
    if operator in {"equals", "contains", "in", "exists"}:
        return "__observed_nonmatching_value__"
    if operator == "not_equals":
        return expected
    if operator in {"gte", "gt"} and isinstance(expected, (int, float)):
        return expected - 1
    if operator in {"lte", "lt"} and isinstance(expected, (int, float)):
        return expected + 1
    if operator == "between" and isinstance(expected, list) and len(expected) == 2:
        return expected[1] + 1
    return "__observed_nonmatching_value__"


def _screening_record(
    source: dict[str, Any], criteria: dict[str, Any], predictions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    text = "\n".join((str(source.get("title") or ""), str(source.get("abstract") or "")))
    fields: dict[str, Any] = {}
    anchors: dict[str, list[str]] = {}
    confidence: dict[str, float] = {}
    for criterion in criteria["criteria"]:
        criterion_id = criterion["criterion_id"]
        field = criterion["predicate"]["field"]
        row = predictions.get(criterion_id)
        if row is None or row["decision"] in {"unclear", "not_reported"}:
            fields[field] = None
            continue
        quote = row["evidence_quote"].strip()
        if not quote or quote.casefold() not in text.casefold():
            fields[field] = None
            continue
        fields[field] = (
            criterion["predicate"]["value"]
            if row["decision"] == "met" else _contradiction(criterion["predicate"])
        )
        anchors[field] = [f"{source['record_id']}-{criterion_id}-title-abstract"]
        confidence[field] = row["confidence"]
    return {
        "assessment_id": f"{source['record_id']}-title-abstract", "record_id": source["record_id"],
        "report_id": None, "fields": fields, "anchors": anchors, "confidence": confidence,
        "counterevidence": {},
    }


def _parse_batch(content: str, allowed_records: set[str], allowed_criteria: set[str]) -> dict[str, dict[str, dict[str, Any]]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JointLifecycleRunError("selection provider returned invalid JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"records"} or not isinstance(payload["records"], list):
        raise JointLifecycleRunError("selection provider output must contain only a records array")
    parsed: dict[str, dict[str, dict[str, Any]]] = {}
    for row in payload["records"]:
        if not isinstance(row, dict) or set(row) != {"record_id", "criteria"}:
            raise JointLifecycleRunError("selection record output shape is invalid")
        record_id = row["record_id"]
        if record_id not in allowed_records or record_id in parsed or not isinstance(row["criteria"], list):
            raise JointLifecycleRunError("selection output contains unknown or duplicate record_id")
        criterion_rows: dict[str, dict[str, Any]] = {}
        for item in row["criteria"]:
            if not isinstance(item, dict) or set(item) != {"criterion_id", "decision", "evidence_quote", "confidence"}:
                raise JointLifecycleRunError("selection criterion output shape is invalid")
            criterion_id = item["criterion_id"]
            if criterion_id not in allowed_criteria or criterion_id in criterion_rows:
                raise JointLifecycleRunError("selection output contains unknown or duplicate criterion_id")
            if item["decision"] not in {"met", "not_met", "unclear", "not_reported"}:
                raise JointLifecycleRunError("selection decision is invalid")
            if not isinstance(item["evidence_quote"], str):
                raise JointLifecycleRunError("selection evidence_quote must be text")
            if isinstance(item["confidence"], bool) or not isinstance(item["confidence"], (int, float)) or not 0 <= item["confidence"] <= 1:
                raise JointLifecycleRunError("selection confidence must be between zero and one")
            criterion_rows[criterion_id] = item
        if set(criterion_rows) != allowed_criteria:
            raise JointLifecycleRunError("selection output did not assess every criterion")
        parsed[record_id] = criterion_rows
    if set(parsed) != allowed_records:
        raise JointLifecycleRunError("selection output did not assess every supplied record")
    return parsed


def complete_record_selection_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *, provider_builder: ProviderBuilder = build_provider,
) -> dict[str, Any]:
    if request.get("stage_id") != "selection" or request.get("ordinal") != 3:
        raise JointLifecycleRunError("selection adapter can execute only canonical stage three")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("selection adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_selection_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    state, search_state_path = _prior_search_state(request, root)
    criteria_path = _bound(root, state["criteria_artifact"], "frozen protocol criteria")
    protocol_path = _bound(root, state["protocol_artifact"], "frozen protocol")
    try:
        criteria = json.loads(criteria_path.read_text(encoding="utf-8"))
        validate_document(criteria, "protocol_criteria")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid frozen protocol criteria: {exc}") from exc
    provider_path = _bound(root, config["provider_config"], "selection provider config")
    provider_config = json.loads(provider_path.read_text(encoding="utf-8"))
    provider = MeteredModelProvider(
        provider_builder(provider_config), meter,
        max_input_tokens_per_call=config["maximum_input_tokens_per_call"],
    )
    records = state["records"]
    criterion_ids = {item["criterion_id"] for item in criteria["criteria"]}
    assessments: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for start in range(0, len(records), config["batch_size"]):
        batch = records[start:start + config["batch_size"]]
        messages = [{
            "role": "user", "content": json.dumps({
                "task": "Assess every title/abstract record against every frozen operational criterion.",
                "rules": [
                    "Use only the supplied title and abstract.",
                    "Quote exact supporting or excluding text for met/not_met.",
                    "Use unclear/not_reported when title/abstract evidence is insufficient.",
                    "Do not infer a target review or published answer.",
                ],
                "criteria": [{
                    "criterion_id": item["criterion_id"], "label": item["label"],
                    "full_text_required": item["full_text_required"],
                } for item in criteria["criteria"]],
                "records": [{
                    "record_id": item["record_id"], "title": item.get("title", ""),
                    "abstract": item.get("abstract", ""),
                } for item in batch],
                "required_output": {"records": [{
                    "record_id": "supplied ID", "criteria": [{
                        "criterion_id": "supplied criterion ID",
                        "decision": "met|not_met|unclear|not_reported",
                        "evidence_quote": "exact title/abstract quote or empty",
                        "confidence": "number 0..1",
                    }],
                }]},
            }, ensure_ascii=False, sort_keys=True),
        }]
        result = provider.chat(
            messages, model="deepseek-v4-flash", thinking=config["thinking"],
            max_tokens=config["maximum_output_tokens_per_call"], json_output=True,
        )
        if result.model != "deepseek-v4-flash":
            raise JointLifecycleRunError("selection stage must use deepseek-v4-flash")
        batch_ids = {item["record_id"] for item in batch}
        schema_status = "valid"
        try:
            predictions = _parse_batch(result.content, batch_ids, criterion_ids)
        except JointLifecycleRunError:
            predictions = {record_id: {} for record_id in batch_ids}
            schema_status = "invalid_abstained_entire_batch"
        for source in batch:
            try:
                assessment = screen_record(
                    criteria, _screening_record(source, criteria, predictions[source["record_id"]]),
                    stage="title_abstract", confidence_floor=config["confidence_floor"],
                    created_at_utc=request["created_at_utc"],
                )
            except ScreeningError as exc:
                raise JointLifecycleRunError(f"deterministic screening policy failed: {exc}") from exc
            assessments.append(assessment)
        audits.append({
            "batch_start": start, "record_ids": sorted(batch_ids), "schema_status": schema_status,
            "model": result.model, "response_sha256": result.content_sha256,
            "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens,
        })
    decisions = {item["record_id"]: item["policy_decision"]["recommendation"] for item in assessments}
    record_ids = [item["record_id"] for item in records]
    if set(decisions) != set(record_ids) or len(decisions) != len(record_ids):
        raise JointLifecycleRunError("selection did not account for every retrieved record exactly once")
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    state_document = {
        "schema_version": "1.0", "stage_id": "selection", "case_id": request["case_id"],
        "arm_id": request["arm_id"], "seed": request["seed"],
        "search_state_artifact": {"path": str(search_state_path), "sha256": _sha(search_state_path)},
        "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
        "criteria_artifact": {"path": str(criteria_path), "sha256": _sha(criteria_path)},
        "record_ids": record_ids, "assessments": assessments,
        "include_record_ids": [key for key, value in decisions.items() if value == "include"],
        "exclude_record_ids": [key for key, value in decisions.items() if value == "exclude"],
        "abstain_record_ids": [key for key, value in decisions.items() if value == "abstain"],
        "all_records_accounted_for": True, "model_provenance": audits,
        "published_reference_accessed": False,
    }
    state_path = output_dir / "selection-state.json"
    atomic_write_json(state_path, state_document, "joint_selection_stage_state")
    artifacts = [{
        "artifact_id": "selection_state", "path": str(state_path), "sha256": _sha(state_path),
        "media_type": "application/json", "role": "stage_state",
    }]
    output = {
        "schema_version": "1.0", "stage_id": "selection", "status": "completed",
        "state_artifact_id": "selection_state", "artifacts": artifacts,
        "scientific_checks": [{
            "check_id": "complete_record_level_selection", "status": "passed",
            "evidence_artifact_ids": ["selection_state"],
        }], "terminal_reason": None,
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
