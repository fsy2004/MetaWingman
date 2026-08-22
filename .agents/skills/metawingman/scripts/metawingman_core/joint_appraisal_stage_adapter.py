"""Build exact-question appraisal dossiers and a deterministic missing-evidence matrix."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from .joint_lifecycle_runner import AtomicStageBudgetMeter, JointLifecycleRunError, MeteredModelProvider
from .judgment_workbench import JudgmentWorkbenchError, build_appraisal_dossier, build_missing_evidence_matrix
from .provider_factory import build_provider
from .schema_guard import SchemaValidationError, validate_document
from .state_store import atomic_write_json


ProviderBuilder = Callable[[dict[str, Any]], Any]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.") or "entity"


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


def _previous(request: dict[str, Any], root: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = Path(str(request.get("previous_output_manifest_path") or "")).resolve(strict=True)
    if _sha(manifest_path) != request.get("previous_output_manifest_sha256"):
        raise JointLifecycleRunError("lineage output manifest hash drift")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        output = manifest["stage_output"]
        matches = [item for item in output["artifacts"] if item["artifact_id"] == output["state_artifact_id"]]
        if len(matches) != 1:
            raise KeyError("lineage state")
        state_path = Path(matches[0]["path"]).resolve(strict=True)
        if _sha(state_path) != matches[0]["sha256"]:
            raise JointLifecycleRunError("lineage state artifact hash drift")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_document(state, "joint_lineage_stage_state")
    except (OSError, json.JSONDecodeError, KeyError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid lineage state: {exc}") from exc
    return state, state_path


def _parse(content: str, adapter: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise JointLifecycleRunError("appraisal provider returned invalid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"domains", "overall_judgment", "overall_rationale"}:
        raise JointLifecycleRunError("appraisal output top-level shape is invalid")
    if not isinstance(value["domains"], list) or not isinstance(value["overall_judgment"], str) or not isinstance(value["overall_rationale"], str):
        raise JointLifecycleRunError("appraisal output values are invalid")
    expected_domains = {item["domain_id"]: set(item["signaling_question_ids"]) for item in adapter["domains"]}
    observed: dict[str, dict[str, Any]] = {}
    for domain in value["domains"]:
        if not isinstance(domain, dict) or set(domain) != {"domain_id", "questions", "proposal", "rationale"}:
            raise JointLifecycleRunError("appraisal domain output shape is invalid")
        domain_id = domain["domain_id"]
        if domain_id not in expected_domains or domain_id in observed or not isinstance(domain["questions"], list):
            raise JointLifecycleRunError("appraisal domain ID is unknown or duplicate")
        questions: dict[str, dict[str, Any]] = {}
        for row in domain["questions"]:
            if not isinstance(row, dict) or set(row) != {"question_id", "answer", "evidence_quote", "rationale"}:
                raise JointLifecycleRunError("appraisal question output shape is invalid")
            question_id = row["question_id"]
            if question_id not in expected_domains[domain_id] or question_id in questions:
                raise JointLifecycleRunError("appraisal question ID is unknown or duplicate")
            if row["answer"] not in adapter["allowed_answers"] or not isinstance(row["evidence_quote"], str) or not isinstance(row["rationale"], str):
                raise JointLifecycleRunError("appraisal question values are invalid")
            questions[question_id] = row
        if set(questions) != expected_domains[domain_id]:
            raise JointLifecycleRunError("appraisal did not answer every signaling question")
        observed[domain_id] = dict(domain) | {"questions": questions}
    if set(observed) != set(expected_domains):
        raise JointLifecycleRunError("appraisal did not assess every domain")
    return dict(value) | {"domains": observed}


def appraisal_missing_evidence_stage_adapter(
    request: dict[str, Any], meter: AtomicStageBudgetMeter, *, provider_builder: ProviderBuilder = build_provider,
) -> dict[str, Any]:
    if request.get("stage_id") != "appraisal" or request.get("ordinal") != 5:
        raise JointLifecycleRunError("appraisal adapter can execute only canonical stage five")
    if request.get("published_reference_accessed") is not False:
        raise JointLifecycleRunError("appraisal adapter refuses published-reference access")
    config = request.get("config")
    try:
        validate_document(config, "joint_appraisal_stage_config")
    except SchemaValidationError as exc:
        raise JointLifecycleRunError(str(exc)) from exc
    root = Path(request["repository_root"]).resolve(strict=True)
    lineage, lineage_path = _previous(request, root)
    protocol_path = _bound(root, lineage["protocol_artifact"], "protocol")
    framework_path = _bound(root, config["framework_adapter"], "appraisal framework adapter")
    question_path = _bound(root, config["question_manifest"], "appraisal question manifest")
    try:
        adapter = json.loads(framework_path.read_text(encoding="utf-8"))
        questions = json.loads(question_path.read_text(encoding="utf-8"))
        validate_document(adapter, "appraisal_framework_adapter")
        validate_document(questions, "joint_appraisal_question_manifest")
    except (OSError, json.JSONDecodeError, SchemaValidationError) as exc:
        raise JointLifecycleRunError(f"invalid appraisal method binding: {exc}") from exc
    if questions["framework_adapter_id"] != adapter["adapter_id"]:
        raise JointLifecycleRunError("appraisal question manifest and framework adapter disagree")
    expected_questions = {question for domain in adapter["domains"] for question in domain["signaling_question_ids"]}
    question_text = {item["question_id"]: item["question"] for item in questions["questions"]}
    if set(question_text) != expected_questions:
        raise JointLifecycleRunError("question manifest does not exactly cover the framework adapter")
    if config["review_family"] not in adapter["supported_review_families"]:
        raise JointLifecycleRunError("framework adapter does not support the frozen review family")
    provider_path = _bound(root, config["provider_config"], "appraisal provider config")
    provider = MeteredModelProvider(
        provider_builder(json.loads(provider_path.read_text(encoding="utf-8"))), meter,
        max_input_tokens_per_call=config["maximum_input_tokens_per_call"],
    )
    document_by_record = {item["record_id"]: item for item in lineage["documents"]}
    report_by_result: dict[str, dict[str, Any]] = {}
    for result in lineage["results"]:
        report = next((item for item in lineage["reports"] if item["record_id"] in document_by_record), None)
        if report is not None:
            report_by_result[result["result_id"]] = report
    dossiers: list[dict[str, Any]] = []
    for result_row in lineage["results"]:
        report = report_by_result.get(result_row["result_id"])
        if report is None:
            continue
        document = document_by_record[report["record_id"]]
        text_binding = document.get("normalized_text_artifact")
        if not isinstance(text_binding, dict):
            continue
        text_path = _bound(root, text_binding, f"full text for {report['record_id']}")
        full_text = text_path.read_text(encoding="utf-8")
        result = provider.chat([{
            "role": "user", "content": json.dumps({
                "task": "Propose a result-level risk-of-bias appraisal using every exact signaling question.",
                "framework": adapter["framework"],
                "domains": [{
                    "domain_id": domain["domain_id"], "label": domain["label"],
                    "questions": [{"question_id": qid, "question": question_text[qid]} for qid in domain["signaling_question_ids"]],
                } for domain in adapter["domains"]],
                "full_text": full_text,
                "rules": [
                    "Use no_information when evidence is absent.",
                    "For every non-no_information answer provide an exact source quote.",
                    "Do not finalize; output a source-bounded proposal only.",
                ],
                "required_output": {
                    "domains": [{"domain_id": "ID", "questions": [{
                        "question_id": "ID", "answer": "allowed answer", "evidence_quote": "exact quote or empty", "rationale": "text",
                    }], "proposal": "domain judgment", "rationale": "text"}],
                    "overall_judgment": "proposal", "overall_rationale": "text",
                },
            }, ensure_ascii=False, sort_keys=True),
        }], model="deepseek-v4-flash", thinking=config["thinking"],
            max_tokens=config["maximum_output_tokens_per_call"], json_output=True)
        if result.model != "deepseek-v4-flash":
            raise JointLifecycleRunError("appraisal stage must use deepseek-v4-flash")
        parsed = _parse(result.content, adapter)
        dossier_domains: list[dict[str, Any]] = []
        all_answers: list[str] = []
        evidence_ids: list[str] = []
        missing: list[str] = []
        for definition in adapter["domains"]:
            domain = parsed["domains"][definition["domain_id"]]
            rows: list[dict[str, Any]] = []
            domain_anchors: list[str] = []
            for qid in definition["signaling_question_ids"]:
                raw = domain["questions"][qid]
                quote = raw["evidence_quote"].strip()
                anchors: list[str] = []
                if raw["answer"] != "no_information":
                    if not quote or quote.casefold() not in full_text.casefold():
                        raw = dict(raw) | {"answer": "no_information", "rationale": "Exact-span verifier could not confirm the proposed evidence."}
                        missing.append(f"unverified_question:{qid}")
                    else:
                        anchor_id = _id(f"appraisal-{result_row['result_id']}-{qid}")
                        anchors = [anchor_id]
                        domain_anchors.append(anchor_id)
                        evidence_ids.append(anchor_id)
                else:
                    missing.append(f"no_information:{qid}")
                all_answers.append(raw["answer"])
                rows.append({
                    "question_id": qid, "question": question_text[qid], "answer": raw["answer"],
                    "anchor_ids": anchors, "rationale": raw["rationale"] or "No rationale supplied; treated conservatively.",
                })
            dossier_domains.append({
                "domain_id": definition["domain_id"], "signaling_questions": rows,
                "supporting_anchor_ids": domain_anchors, "counterevidence_anchor_ids": [],
                "proposal": domain["proposal"] or "Unresolved", "rationale": domain["rationale"] or "Conservative unresolved appraisal.",
            })
        adverse = any(answer in {"no", "probably_no"} for answer in all_answers)
        unknown = any(answer == "no_information" for answer in all_answers)
        judge = "high_or_serious_concern" if adverse else "unclear" if unknown else "low_concern_candidate"
        opposition = "deterministic_challenge" if adverse or unknown else "no_deterministic_challenge"
        candidate = {
            "dossier_id": _id(f"appraisal-{result_row['result_id']}"), "dossier_type": "risk_of_bias",
            "review_family": config["review_family"],
            "target": {"type": adapter["target_granularity"], "id": result_row["result_id"], "study_id": result_row["study_id"], "result_id": result_row["result_id"], "synthesis_id": None},
            "domains": dossier_domains, "evidence_node_ids": list(dict.fromkeys(evidence_ids)) or [f"document:{report['record_id']}"],
            "overall_proposal": {"actor_id": "deepseek-v4-flash", "judgment": parsed["overall_judgment"] or "Unresolved", "rationale": parsed["overall_rationale"] or "Model proposal."},
            "opposition": {"actor_id": "exact-span-conservative-opposition-v1", "counter_judgment": opposition, "anchor_ids": list(dict.fromkeys(evidence_ids)), "rationale": "Deterministic opposition challenges missing, unanchored, and adverse signaling answers."},
            "judge_recommendation": {"actor_id": "conservative-domain-logic-v1", "judgment": judge, "reason_codes": ["exact_span_domain_logic"], "confidence": None, "abstained": unknown},
            "missing_information": missing,
        }
        try:
            dossiers.append(build_appraisal_dossier(adapter, candidate, created_at_utc=request["created_at_utc"]))
        except JudgmentWorkbenchError as exc:
            raise JointLifecycleRunError(f"appraisal dossier failed: {exc}") from exc
    expected_results = []
    for result in lineage["results"]:
        estimand = next(item for item in lineage["estimands"] if item["estimand_id"] == result["estimand_id"])
        candidate_ids = [item["candidate_id"] for item in lineage["extraction_candidates"] if item["result_id"] == result["result_id"]]
        anchors = [anchor for item in lineage["extraction_candidates"] if item["result_id"] == result["result_id"] for anchor in item["anchor_ids"]]
        expected_results.append({
            "study_id": result["study_id"], "result_key": result["result_id"], "outcome": estimand["outcome"],
            "timepoint": estimand["time_window"], "contrast": estimand["contrast"], "planned_source_ids": [],
            "availability": "available" if candidate_ids else "unavailable", "identified_result_ids": [result["result_id"]],
            "included_result_ids": [result["result_id"]] if candidate_ids else [], "anchor_ids": anchors,
            "reason": "Verified result primitives were available." if candidate_ids else "No verified result primitive was available.",
            "selective_nonreporting_signal": "unclear" if lineage["unresolved_record_ids"] else "none",
        })
    judgment = "unclear_due_to_unresolved_records" if lineage["unresolved_record_ids"] else "no_observed_missing_result_signal"
    role = lambda actor: {"actor_id": actor, "judgment": judgment, "reason_codes": ["observed_availability_audit"], "anchor_ids": [], "rationale": "Compared expected frozen estimands with verified result lineage; does not infer unobserved studies.", "abstained": bool(lineage["unresolved_record_ids"])}
    matrix_candidate = {
        "matrix_id": _id(f"missing-{request['case_id']}-{request['arm_id']}-{request['seed']}"), "synthesis_id": "synthesis-01",
        "framework": {"name": "project_availability_audit", "version": "1.0", "source_url": "https://metawingman.local/methods/project-availability-audit-v1", "verified_at_utc": request["created_at_utc"]},
        "expected_results": expected_results, "study_level_flags": [],
        "proposal": role("observed-availability-proposal-v1"), "opposition": role("unobserved-study-opposition-v1"),
        "judge_recommendation": role("conservative-missing-evidence-judge-v1"),
    }
    try:
        matrix = build_missing_evidence_matrix(matrix_candidate, created_at_utc=request["created_at_utc"])
    except JudgmentWorkbenchError as exc:
        raise JointLifecycleRunError(f"missing-evidence matrix failed: {exc}") from exc
    ready = sum(item["status"] == "ready_for_adjudication" for item in dossiers)
    complete = bool(dossiers) and ready == len(dossiers) and matrix["status"] == "ready_for_adjudication"
    state = {
        "schema_version": "1.0", "stage_id": "appraisal", "case_id": request["case_id"], "arm_id": request["arm_id"], "seed": request["seed"],
        "lineage_state_artifact": {"path": str(lineage_path), "sha256": _sha(lineage_path)},
        "protocol_artifact": {"path": str(protocol_path), "sha256": _sha(protocol_path)},
        "framework_adapter_sha256": _sha(framework_path), "appraisal_dossiers": dossiers,
        "missing_evidence_matrix": matrix, "deterministic_opposition_policy": "exact-span-plus-conservative-domain-logic-v1",
        "ready_dossier_count": ready, "published_reference_accessed": False,
    }
    output_dir = Path(request["stage_output_dir"]).resolve(strict=True)
    state_path = output_dir / "appraisal-state.json"
    atomic_write_json(state_path, state, "joint_appraisal_stage_state")
    artifacts = [{"artifact_id": "appraisal_state", "path": str(state_path), "sha256": _sha(state_path), "media_type": "application/json", "role": "stage_state"}]
    status = "completed" if complete else "abstained"
    output = {
        "schema_version": "1.0", "stage_id": "appraisal", "status": status,
        "state_artifact_id": "appraisal_state", "artifacts": artifacts,
        "scientific_checks": [{"check_id": "appraisal_and_missing_evidence_complete", "status": "passed" if complete else "abstained", "evidence_artifact_ids": ["appraisal_state"]}],
        "terminal_reason": None if complete else "no complete source-bound appraisal dossier",
    }
    validate_document(output, "joint_lifecycle_stage_output")
    return output
