"""Cross-object scientific invariants for the MetaWingman method contract."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


PLACEHOLDER_VERSIONS = {"", "current", "latest", "living", "n/a", "na", "none", "tbd", "unknown"}
AUTHORITY_ROLES = {"conduct", "reporting", "appraisal", "certainty"}
REVIEW_TASKS = {
    "title_abstract_screening",
    "full_text_eligibility",
    "outcome_data_extraction",
    "risk_of_bias",
    "certainty",
    "poolability",
    "final_conclusion",
}


def _duplicates(values: Sequence[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _index(records: Sequence[dict[str, Any]], key: str, label: str, issues: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        value = str(record.get(key, ""))
        if value in result:
            issues.append(f"{label}: duplicate {key} {value}")
        result[value] = record
    return result


def _artifact_path(root: Path, relative: str, label: str, issues: list[str]) -> Path | None:
    if not relative:
        issues.append(f"{label}: artifact path is empty")
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        issues.append(f"{label}: artifact path escapes project root: {relative}")
        return None
    return candidate


def _verify_artifact(
    root: Path,
    relative: str,
    expected_sha256: str,
    label: str,
    issues: list[str],
) -> None:
    candidate = _artifact_path(root, relative, label, issues)
    if candidate is None:
        return
    if not candidate.is_file():
        issues.append(f"{label}: artifact is missing: {relative}")
        return
    actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
    if actual != expected_sha256:
        issues.append(f"{label}: sha256 mismatch: {relative}")


def _check_profile(profile: dict[str, Any], issues: list[str]) -> None:
    mode = profile["operating_mode"]
    rules = profile["independent_review"]
    authority_ids = [authority["authority_id"] for authority in profile["authorities"]]
    for duplicate in sorted(_duplicates(authority_ids)):
        issues.append(f"review_profile: duplicate authority_id {duplicate}")
    task_types = [rule["task_type"] for rule in rules]
    for duplicate in sorted(_duplicates(task_types)):
        issues.append(f"review_profile: duplicate independent-review rule for {duplicate}")

    for rule in rules:
        task = rule["task_type"]
        required = rule["independent_human_required"]
        minimum = rule["minimum_independent_humans"]
        if required and minimum < 1:
            issues.append(f"review_profile: {task} requires an independent human but minimum is zero")
        if not required and minimum != 0:
            issues.append(f"review_profile: {task} has a human minimum but is not marked human-required")
        if mode["name"] == "assurance" and required and rule["ai_may_replace_human"]:
            issues.append(f"review_profile: assurance mode cannot let AI replace the required human for {task}")

    if mode["name"] == "evaluation" and profile["status"] == "pinned":
        if not mode["replacement_claim"].strip():
            issues.append("review_profile: evaluation mode requires an explicit replacement claim")
        if not mode["evaluation_plan_id"]:
            issues.append("review_profile: evaluation mode requires a preregistered evaluation_plan_id")

    if profile["status"] != "pinned":
        return
    for task in sorted(REVIEW_TASKS - set(task_types)):
        issues.append(f"review_profile: pinned profile has no independent-review rule for {task}")
    final_rule = next((rule for rule in rules if rule["task_type"] == "final_conclusion"), None)
    if final_rule:
        if not final_rule["independent_human_required"] or final_rule["minimum_independent_humans"] < 1:
            issues.append("review_profile: final_conclusion requires at least one responsible human")
        if final_rule["ai_may_replace_human"]:
            issues.append("review_profile: AI cannot replace final scientific responsibility")
    if not mode["declared_by"].strip():
        issues.append("review_profile: pinned profile has no operating-mode declarant")
    roles_present = {authority["role"] for authority in profile["authorities"]}
    for role in sorted(AUTHORITY_ROLES - roles_present):
        issues.append(f"review_profile: pinned profile has no {role} authority or not-applicable record")
    applicable_roles = {
        authority["role"]
        for authority in profile["authorities"]
        if authority["applicability"] == "applicable"
    }
    for role in ("conduct", "reporting"):
        if role not in applicable_roles:
            issues.append(f"review_profile: pinned profile requires an applicable {role} authority")
    for authority in profile["authorities"]:
        if authority["applicability"] != "applicable":
            continue
        version = authority["version"].strip().lower()
        if version in PLACEHOLDER_VERSIONS:
            issues.append(
                f"review_profile: applicable authority {authority['authority_id']} needs an exact version"
            )


def _check_protocol(
    root: Path,
    profile: dict[str, Any],
    protocol: dict[str, Any],
    criteria: dict[str, Any] | None,
    review_state: dict[str, Any] | None,
    issues: list[str],
) -> None:
    if protocol["profile_id"] != profile["profile_id"]:
        issues.append("protocol: profile_id does not match review_profile.json")

    review_question_ids = [item["question_id"] for item in protocol["review_questions"]]
    outcome_ids = [item["outcome_id"] for item in protocol["outcome_hierarchy"]]
    synthesis_ids = [item["synthesis_id"] for item in protocol["synthesis_questions"]]
    estimand_ids = [item["estimand"]["estimand_id"] for item in protocol["synthesis_questions"]]
    source_ids = [item["source_id"] for item in protocol["source_plan"]]
    for label, values in (
        ("review question", review_question_ids),
        ("outcome", outcome_ids),
        ("synthesis question", synthesis_ids),
        ("estimand", estimand_ids),
        ("source", source_ids),
    ):
        for duplicate in sorted(_duplicates(values)):
            issues.append(f"protocol: duplicate {label} ID {duplicate}")

    review_question_set = set(review_question_ids)
    outcome_set = set(outcome_ids)
    for synthesis in protocol["synthesis_questions"]:
        threshold_ids = [item["threshold_id"] for item in synthesis["decision_thresholds"]]
        for duplicate in sorted(_duplicates(threshold_ids)):
            issues.append(
                f"protocol: synthesis {synthesis['synthesis_id']} has duplicate threshold ID {duplicate}"
            )
        unknown_questions = set(synthesis["review_question_ids"]) - review_question_set
        if unknown_questions:
            issues.append(
                f"protocol: synthesis {synthesis['synthesis_id']} references unknown review questions "
                f"{sorted(unknown_questions)}"
            )
        if synthesis["outcome_id"] not in outcome_set:
            issues.append(
                f"protocol: synthesis {synthesis['synthesis_id']} references unknown outcome "
                f"{synthesis['outcome_id']}"
            )

    artifact = protocol["criteria_artifact"]
    if criteria is not None:
        criterion_ids = [item["criterion_id"] for item in criteria["criteria"]]
        for duplicate in sorted(_duplicates(criterion_ids)):
            issues.append(f"protocol: duplicate criterion ID {duplicate}")
        if criteria["protocol_version"] != protocol["protocol_version"]:
            issues.append("protocol: protocol_criteria.json version does not match protocol.json")
        if artifact["status"] != criteria["status"]:
            issues.append("protocol: criteria artifact status does not match protocol_criteria.json")
    if artifact["sha256"]:
        _verify_artifact(root, artifact["path"], artifact["sha256"], "protocol criteria", issues)

    frozen = protocol["status"] in {"frozen", "amended"}
    if frozen and profile["status"] != "pinned":
        issues.append("protocol: a frozen or amended protocol requires a pinned review profile")
    if frozen:
        if criteria is None:
            issues.append("protocol: frozen protocol has no compiled eligibility criteria")
        else:
            if criteria["status"] not in {"frozen", "amended"}:
                issues.append("protocol: frozen protocol has non-frozen eligibility criteria")
            if not criteria["criteria"]:
                issues.append("protocol: frozen protocol has no eligibility criteria")
            unresolved = [
                item["criterion_id"]
                for item in criteria["criteria"]
                if item["status"] != "operational"
            ]
            if unresolved:
                issues.append(f"protocol: frozen protocol has non-operational criteria {unresolved}")
        if not artifact["sha256"]:
            issues.append("protocol: frozen protocol has no criteria artifact hash")
    if review_state:
        state_protocol = review_state["protocol"]
        if state_protocol["version"] != protocol["protocol_version"]:
            issues.append("protocol: version diverges from review_state.json")
        if state_protocol["status"] != protocol["status"]:
            issues.append("protocol: status diverges from review_state.json")
        protocol_path = root / "01_protocol/protocol.json"
        if protocol_path.is_file() and state_protocol["sha256"]:
            actual_protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
            if state_protocol["sha256"] != actual_protocol_sha256:
                issues.append("protocol: review_state sha256 does not match protocol.json")


def _check_assignments(
    profile: dict[str, Any],
    assignments: Sequence[dict[str, Any]],
    gates: Mapping[str, Any],
    issues: list[str],
) -> None:
    rules = {rule["task_type"]: rule for rule in profile["independent_review"]}
    seen_actor_groups: dict[tuple[str, str, int, str], str] = {}
    completed: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)

    for assignment in assignments:
        task = assignment["task_type"]
        rule = rules.get(task)
        if not rule:
            issues.append(
                f"reviewer_assignment {assignment['assignment_id']}: task has no profile rule"
            )
        if rule and assignment["independent_human_required"] != rule["independent_human_required"]:
            issues.append(
                f"reviewer_assignment {assignment['assignment_id']}: human-requirement flag diverges from profile"
            )
        if assignment["status"] == "completed" and assignment["conflict_of_interest"]["status"] == "present_unmanaged":
            issues.append(f"reviewer_assignment {assignment['assignment_id']}: completed with unmanaged conflict")
        if (
            rule
            and rule["required_ai_exposure_order"] == "blinded_before_ai"
            and assignment["actor"]["type"] == "human"
            and assignment["ai_exposure"]["order"] not in {"blinded_before_ai", "not_exposed"}
        ):
            issues.append(
                f"reviewer_assignment {assignment['assignment_id']}: violates blinded-before-AI order"
            )
        exposure = assignment["ai_exposure"]
        if exposure["order"] in {"not_exposed", "not_applicable"} and exposure["exposed_to_ai_output_ids"]:
            issues.append(
                f"reviewer_assignment {assignment['assignment_id']}: records AI outputs despite no exposure"
            )

        for artifact_id in assignment["artifact_ids"]:
            actor_key = (task, artifact_id, assignment["round"], assignment["actor"]["id"])
            previous_group = seen_actor_groups.get(actor_key)
            if previous_group and previous_group != assignment["independence_group"]:
                issues.append(
                    f"reviewer_assignment: actor {assignment['actor']['id']} is counted in multiple "
                    f"independence groups for {task}/{artifact_id}"
                )
            seen_actor_groups[actor_key] = assignment["independence_group"]
            if assignment["status"] == "completed":
                completed[(task, artifact_id, assignment["round"])].append(assignment)

    stage_for_task = {
        "title_abstract_screening": "3",
        "full_text_eligibility": "3",
        "outcome_data_extraction": "4",
        "risk_of_bias": "5",
        "poolability": "6",
        "certainty": "7",
        "final_conclusion": "8",
    }
    for task, stage in stage_for_task.items():
        rule = rules.get(task)
        if (
            rule
            and gates.get(stage, {}).get("status") == "complete"
            and not any(key[0] == task for key in completed)
        ):
            issues.append(
                f"reviewer_assignment: completed stage {stage} has no completed {task} assignment"
            )
    for key, task_assignments in completed.items():
        task, artifact_id, _round = key
        rule = rules.get(task)
        if not rule or not rule["independent_human_required"]:
            continue
        replacement_allowed = (
            profile["operating_mode"]["name"] == "evaluation"
            and rule["ai_may_replace_human"]
        )
        if replacement_allowed:
            continue
        if gates.get(stage_for_task[task], {}).get("status") != "complete":
            continue
        human_actor_ids = {
            assignment["actor"]["id"]
            for assignment in task_assignments
            if assignment["actor"]["type"] == "human"
            and assignment["counts_toward_independent_human_requirement"]
        }
        human_groups = {
            assignment["independence_group"]
            for assignment in task_assignments
            if assignment["actor"]["type"] == "human"
            and assignment["counts_toward_independent_human_requirement"]
        }
        qualifying_humans = min(len(human_actor_ids), len(human_groups))
        if qualifying_humans < rule["minimum_independent_humans"]:
            issues.append(
                f"reviewer_assignment: {task}/{artifact_id} has {qualifying_humans} qualifying independent "
                f"humans; profile requires {rule['minimum_independent_humans']}"
            )


def _check_deviations(deviations: Sequence[dict[str, Any]], issues: list[str]) -> None:
    _index(deviations, "deviation_id", "protocol_deviation", issues)
    for deviation in deviations:
        if deviation["status"] != "resolved":
            continue
        incomplete = [
            item["artifact_or_stage"]
            for item in deviation["required_reruns"]
            if item["status"] not in {"complete", "not_applicable"}
        ]
        if incomplete:
            issues.append(
                f"protocol_deviation {deviation['deviation_id']}: resolved with incomplete reruns {incomplete}"
            )


def _check_document_states(
    root: Path,
    documents: Sequence[dict[str, Any]],
    issues: list[str],
) -> dict[str, dict[str, Any]]:
    indexed = _index(documents, "document_id", "document_state", issues)
    for document in documents:
        source = document["source"]
        _verify_artifact(
            root,
            source["artifact_path"],
            source["sha256"],
            f"document_state {document['document_id']} source",
            issues,
        )
        representation_ids = [item["representation_id"] for item in document["representations"]]
        for duplicate in sorted(_duplicates(representation_ids)):
            issues.append(f"document_state {document['document_id']}: duplicate representation {duplicate}")
        if document["active_parse_id"]:
            active = [
                item for item in document["representations"]
                if item["representation_id"] == document["active_parse_id"]
            ]
            if not active:
                issues.append(f"document_state {document['document_id']}: active_parse_id does not exist")
            elif active[0]["status"] != "active":
                issues.append(f"document_state {document['document_id']}: active parse is not marked active")
        for representation in document["representations"]:
            known_derivation_ids = set(representation_ids) | {document["document_id"]}
            unknown_derivations = set(representation["derived_from"]) - known_derivation_ids
            if unknown_derivations:
                issues.append(
                    f"document_state {document['document_id']} representation "
                    f"{representation['representation_id']}: unknown derived_from IDs "
                    f"{sorted(unknown_derivations)}"
                )
            pages = representation["pages"]
            if pages and pages["first"] > pages["last"]:
                issues.append(
                    f"document_state {document['document_id']} representation "
                    f"{representation['representation_id']}: first page exceeds last page"
                )
            _verify_artifact(
                root,
                representation["artifact_path"],
                representation["sha256"],
                f"document_state {document['document_id']} representation {representation['representation_id']}",
                issues,
            )
        parent_id = document["parent_document_id"]
        if parent_id and parent_id not in indexed:
            issues.append(f"document_state {document['document_id']}: unknown parent_document_id {parent_id}")
    for document in documents:
        visited = {document["document_id"]}
        parent_id = document["parent_document_id"]
        while parent_id:
            if parent_id in visited:
                issues.append(f"document_state {document['document_id']}: parent cycle detected")
                break
            visited.add(parent_id)
            parent = indexed.get(parent_id)
            parent_id = parent["parent_document_id"] if parent else None
    return indexed


def _check_evidence_objects(
    streams: Mapping[str, Sequence[dict[str, Any]]],
    document_index: Mapping[str, dict[str, Any]],
    issues: list[str],
) -> None:
    anchor_index = _index(streams.get("evidence_anchor", []), "anchor_id", "evidence_anchor", issues)
    assertion_index = _index(streams.get("evidence_assertion", []), "assertion_id", "evidence_assertion", issues)
    _index(streams.get("lineage_edge", []), "edge_id", "lineage_edge", issues)
    _index(streams.get("extraction_candidate", []), "candidate_id", "extraction_candidate", issues)
    dossier_index = _index(streams.get("appraisal_dossier", []), "dossier_id", "appraisal_dossier", issues)
    _index(streams.get("analysis_manifest", []), "analysis_id", "analysis_manifest", issues)
    _index(streams.get("claim", []), "claim_id", "claim", issues)

    anchor_ids = set(anchor_index)
    assertion_ids = set(assertion_index)
    dossier_ids = set(dossier_index)
    known_evidence_refs = anchor_ids | assertion_ids | dossier_ids

    if "document_state" in streams:
        reports: dict[str, set[str]] = defaultdict(set)
        for document in document_index.values():
            reports[document["report_id"]].add(document["source"]["sha256"])
            reports[document["report_id"]].update(
                item["sha256"] for item in document["representations"]
            )
        for anchor in streams.get("evidence_anchor", []):
            if anchor["report_id"] not in reports:
                issues.append(
                    f"evidence_anchor {anchor['anchor_id']}: report has no document_state record"
                )
            elif anchor["source_sha256"] not in reports[anchor["report_id"]]:
                issues.append(
                    f"evidence_anchor {anchor['anchor_id']}: source_sha256 is absent from document state"
                )

    for assertion in streams.get("evidence_assertion", []):
        unknown = set(assertion["anchor_ids"]) - anchor_ids
        if unknown:
            issues.append(f"evidence_assertion {assertion['assertion_id']}: unknown anchors {sorted(unknown)}")

    for edge in streams.get("lineage_edge", []):
        if edge["from_node"] == edge["to_node"]:
            issues.append(f"lineage_edge {edge['edge_id']}: self-edge is not allowed")
        unknown = set(edge["evidence_refs"]) - known_evidence_refs
        if unknown:
            issues.append(f"lineage_edge {edge['edge_id']}: unknown evidence refs {sorted(unknown)}")
        if edge["status"] == "accepted":
            provisional_refs = [
                ref
                for ref in edge["evidence_refs"]
                if (
                    ref in assertion_index
                    and assertion_index[ref]["status"] != "accepted"
                ) or (
                    ref in dossier_index
                    and dossier_index[ref]["status"] != "final"
                )
            ]
            if provisional_refs:
                issues.append(
                    f"lineage_edge {edge['edge_id']}: accepted edge uses provisional evidence "
                    f"{provisional_refs}"
                )

    for candidate in streams.get("extraction_candidate", []):
        unknown = set(candidate["anchor_ids"]) - anchor_ids
        if unknown:
            issues.append(f"extraction_candidate {candidate['candidate_id']}: unknown anchors {sorted(unknown)}")
        document = document_index.get(candidate["document_id"])
        if not document:
            issues.append(
                f"extraction_candidate {candidate['candidate_id']}: unknown document {candidate['document_id']}"
            )
        elif document["report_id"] != candidate["report_id"]:
            issues.append(
                f"extraction_candidate {candidate['candidate_id']}: report_id diverges from document state"
            )

    for dossier in streams.get("appraisal_dossier", []):
        refs: set[str] = set()
        for domain in dossier["domains"]:
            refs.update(domain["supporting_anchor_ids"])
            refs.update(domain["counterevidence_anchor_ids"])
            for question in domain["signaling_questions"]:
                refs.update(question["anchor_ids"])
        refs.update(dossier["opposition"]["anchor_ids"])
        unknown = refs - anchor_ids
        if unknown:
            issues.append(f"appraisal_dossier {dossier['dossier_id']}: unknown anchors {sorted(unknown)}")
        if dossier["status"] in {"ready_for_adjudication", "final"}:
            actors = {
                dossier["overall_proposal"]["actor_id"],
                dossier["opposition"]["actor_id"],
                dossier["judge_recommendation"]["actor_id"],
            }
            if len(actors) != 3:
                issues.append(
                    f"appraisal_dossier {dossier['dossier_id']}: proposal, opposition, and judge "
                    "must be separately identified actors"
                )
        if dossier["framework"]["version"].strip().lower() in PLACEHOLDER_VERSIONS:
            issues.append(
                f"appraisal_dossier {dossier['dossier_id']}: framework needs an exact version"
            )


def _check_analysis_manifests(
    root: Path,
    protocol: dict[str, Any],
    review_state: dict[str, Any] | None,
    manifests: Sequence[dict[str, Any]],
    issues: list[str],
) -> dict[str, bool]:
    output_verification: dict[str, bool] = {}
    estimand_ids = {
        question["estimand"]["estimand_id"]
        for question in protocol["synthesis_questions"]
    }
    synthesis_ids = {question["synthesis_id"] for question in protocol["synthesis_questions"]}
    freezes = {
        item["freeze_id"]: item
        for item in review_state.get("freezes", [])
    } if review_state else {}
    for manifest in manifests:
        for software in manifest["software"]:
            if software["version"].strip().lower() in PLACEHOLDER_VERSIONS:
                issues.append(
                    f"analysis_manifest {manifest['analysis_id']}: software {software['name']} "
                    "needs an exact version"
                )
        if manifest["synthesis_id"] not in synthesis_ids:
            issues.append(
                f"analysis_manifest {manifest['analysis_id']}: unknown synthesis_id {manifest['synthesis_id']}"
            )
        if manifest["estimand_id"] not in estimand_ids:
            issues.append(
                f"analysis_manifest {manifest['analysis_id']}: unknown estimand_id {manifest['estimand_id']}"
            )
        if manifest["protocol"]["version"] != protocol["protocol_version"]:
            issues.append(f"analysis_manifest {manifest['analysis_id']}: protocol version mismatch")
        if (
            review_state
            and manifest["status"] in {"frozen", "executed", "verified"}
            and manifest["protocol"]["sha256"] != review_state["protocol"]["sha256"]
        ):
            issues.append(
                f"analysis_manifest {manifest['analysis_id']}: protocol hash diverges from review state"
            )
        if manifest["status"] in {"frozen", "executed", "verified"} and review_state:
            protocol_freeze = freezes.get(manifest["protocol"]["freeze_id"])
            if not protocol_freeze or protocol_freeze["kind"] != "protocol":
                issues.append(
                    f"analysis_manifest {manifest['analysis_id']}: unknown protocol freeze_id"
                )
            elif protocol_freeze["sha256"] != manifest["protocol"]["sha256"]:
                issues.append(
                    f"analysis_manifest {manifest['analysis_id']}: protocol hash diverges from freeze"
                )
        if manifest["status"] in {"frozen", "executed", "verified"}:
            for item in manifest["inputs"]:
                if review_state:
                    data_freeze = freezes.get(item["freeze_id"])
                    if not data_freeze or data_freeze["kind"] != "data":
                        issues.append(
                            f"analysis_manifest {manifest['analysis_id']}: unknown data freeze_id "
                            f"{item['freeze_id']}"
                        )
                _verify_artifact(
                    root,
                    item["artifact_path"],
                    item["sha256"],
                    f"analysis_manifest {manifest['analysis_id']} input",
                    issues,
                )
        if manifest["status"] in {"executed", "verified"}:
            planned_output_ids = {
                output_id
                for step in manifest["planned_analyses"]
                for output_id in step["output_ids"]
            }
            actual_output_ids = {output["output_id"] for output in manifest["outputs"]}
            if planned_output_ids != actual_output_ids:
                issues.append(
                    f"analysis_manifest {manifest['analysis_id']}: planned and actual output IDs diverge"
                )
            for output in manifest["outputs"]:
                if output["output_id"] in output_verification:
                    issues.append(f"analysis_manifest: duplicate output_id {output['output_id']}")
                output_verification[output["output_id"]] = manifest["status"] == "verified"
                _verify_artifact(
                    root,
                    output["artifact_path"],
                    output["sha256"],
                    f"analysis_manifest {manifest['analysis_id']} output",
                    issues,
                )
    return output_verification


def _check_claims(
    claims: Sequence[dict[str, Any]],
    assertions: Mapping[str, dict[str, Any]],
    dossiers: Mapping[str, dict[str, Any]],
    output_verification: Mapping[str, bool],
    issues: list[str],
) -> None:
    for claim in claims:
        unknown_assertions = set(claim["assertion_ids"]) - set(assertions)
        if unknown_assertions:
            issues.append(f"claim {claim['claim_id']}: unknown assertions {sorted(unknown_assertions)}")
        unknown_outputs = set(claim["analysis_output_ids"]) - set(output_verification)
        if unknown_outputs:
            issues.append(f"claim {claim['claim_id']}: unknown analysis outputs {sorted(unknown_outputs)}")
        dossier_id = claim["certainty"]["dossier_id"]
        if dossier_id and dossier_id not in dossiers:
            issues.append(f"claim {claim['claim_id']}: unknown certainty dossier {dossier_id}")
        if claim["status"] not in {"accepted", "final"}:
            continue
        unverified_outputs = [
            output_id
            for output_id in claim["analysis_output_ids"]
            if output_id in output_verification and not output_verification[output_id]
        ]
        if unverified_outputs:
            issues.append(
                f"claim {claim['claim_id']}: references unverified analysis outputs "
                f"{unverified_outputs}"
            )
        if not claim["assertion_ids"] and not claim["analysis_output_ids"]:
            issues.append(
                f"claim {claim['claim_id']}: accepted claim has no accepted assertion or verified analysis output"
            )
        synthesis_id = claim["scope"]["synthesis_id"]
        if synthesis_id and synthesis_id not in claim["evidence_node_ids"]:
            issues.append(
                f"claim {claim['claim_id']}: scoped synthesis is absent from evidence_node_ids"
            )
        unaccepted_assertions = [
            assertion_id
            for assertion_id in claim["assertion_ids"]
            if assertion_id in assertions and assertions[assertion_id]["status"] != "accepted"
        ]
        if unaccepted_assertions:
            issues.append(
                f"claim {claim['claim_id']}: references non-accepted assertions {unaccepted_assertions}"
            )
        if not dossier_id:
            issues.append(f"claim {claim['claim_id']}: accepted claim has no certainty dossier")
        elif dossier_id in dossiers:
            dossier = dossiers[dossier_id]
            if dossier["dossier_type"] != "certainty" or dossier["status"] != "final":
                issues.append(
                    f"claim {claim['claim_id']}: certainty dossier is not a final certainty judgment"
                )
            elif claim["certainty"]["judgment"] != dossier["final_judgment"]:
                issues.append(
                    f"claim {claim['claim_id']}: certainty judgment diverges from dossier"
                )
            if claim["certainty"]["framework"] != dossier["framework"]["name"]:
                issues.append(
                    f"claim {claim['claim_id']}: certainty framework diverges from dossier"
                )


def inspect_method_contract(
    root: Path,
    documents: Mapping[str, dict[str, Any]],
    streams: Mapping[str, Sequence[dict[str, Any]]],
    gates: Mapping[str, Any],
) -> list[str]:
    """Return cross-object contract violations for already schema-valid objects."""

    root = root.resolve()
    issues: list[str] = []
    profile = documents.get("review_profile")
    protocol = documents.get("protocol")
    criteria = documents.get("protocol_criteria")
    review_state = documents.get("review_state")

    completed_stages = [
        stage for stage in range(10)
        if gates.get(str(stage), {}).get("status") == "complete"
    ]
    if review_state:
        current_stage = review_state["stage"]
        missing_before_current = [
            stage for stage in range(current_stage)
            if gates.get(str(stage), {}).get("status") != "complete"
        ]
        if missing_before_current:
            issues.append(
                f"review_state: current stage {current_stage} skips incomplete stages "
                f"{missing_before_current}"
            )
        completed_after_current = [
            stage for stage in completed_stages if stage > current_stage
        ]
        if completed_after_current:
            issues.append(
                f"review_state: completed stages {completed_after_current} exceed current stage "
                f"{current_stage}"
            )
    for stage in completed_stages:
        incomplete_predecessors = [
            previous for previous in range(stage)
            if gates.get(str(previous), {}).get("status") != "complete"
        ]
        if incomplete_predecessors:
            issues.append(
                f"review_state: stage {stage} is complete before stages {incomplete_predecessors}"
            )
    if gates.get("1", {}).get("status") == "complete":
        if not profile or profile["status"] != "pinned":
            issues.append("review_state: protocol gate is complete without a pinned review profile")
        if not protocol or protocol["status"] not in {"frozen", "amended"}:
            issues.append("review_state: protocol gate is complete without a frozen protocol")
        if not criteria or criteria["status"] not in {"frozen", "amended"}:
            issues.append("review_state: protocol gate is complete without frozen eligibility criteria")

    if profile:
        _check_profile(profile, issues)
        _check_assignments(profile, streams.get("reviewer_assignment", []), gates, issues)
        if review_state and review_state["profile"] != profile["review_family"]:
            issues.append("review_state: review family diverges from review_profile.json")
    if profile and protocol:
        _check_protocol(root, profile, protocol, criteria, review_state, issues)
    _check_deviations(streams.get("protocol_deviation", []), issues)
    document_index = _check_document_states(root, streams.get("document_state", []), issues)
    _check_evidence_objects(streams, document_index, issues)

    assertions = {
        item["assertion_id"]: item for item in streams.get("evidence_assertion", [])
    }
    dossiers = {
        item["dossier_id"]: item for item in streams.get("appraisal_dossier", [])
    }
    output_verification: dict[str, bool] = {}
    if protocol:
        output_verification = _check_analysis_manifests(
            root,
            protocol,
            review_state,
            streams.get("analysis_manifest", []),
            issues,
        )
    _check_claims(
        streams.get("claim", []),
        assertions,
        dossiers,
        output_verification,
        issues,
    )
    return issues


def inspect_protocol_freeze_readiness(
    root: Path,
    profile: dict[str, Any],
    protocol: dict[str, Any],
    criteria: dict[str, Any],
    review_state: dict[str, Any],
    action_input_sha256: str,
) -> list[str]:
    """Return reasons that the current draft cannot be frozen yet."""

    root = root.resolve()
    issues = inspect_method_contract(
        root,
        {
            "review_profile": profile,
            "protocol": protocol,
            "protocol_criteria": criteria,
            "review_state": review_state,
        },
        {},
        review_state["gates"],
    )
    if profile["status"] != "pinned":
        issues.append("review_profile is not pinned")
    if protocol["status"] != "draft":
        issues.append("only a draft protocol can enter the initial freeze action")

    context = protocol["decision_context"]
    for field in ("decision", "setting", "intended_use"):
        if not context[field].strip():
            issues.append(f"protocol decision_context.{field} is empty")
    if not context["stakeholders"]:
        issues.append("protocol decision_context.stakeholders is empty")
    if not protocol["review_questions"]:
        issues.append("protocol has no review question")
    if not protocol["synthesis_questions"]:
        issues.append("protocol has no synthesis question or estimand")
    if not protocol["outcome_hierarchy"]:
        issues.append("protocol has no outcome hierarchy")
    if not protocol["source_plan"]:
        issues.append("protocol has no information-source plan")
    for synthesis in protocol["synthesis_questions"]:
        if not synthesis["decision_thresholds"]:
            issues.append(
                f"synthesis {synthesis['synthesis_id']} has no prespecified decision threshold"
            )
    if not criteria["criteria"]:
        issues.append("protocol has no compiled eligibility criteria")
    unresolved = [
        item["criterion_id"]
        for item in criteria["criteria"]
        if item["status"] != "operational"
    ]
    if unresolved:
        issues.append(f"protocol has non-operational criteria {unresolved}")

    criteria_path = _artifact_path(
        root,
        protocol["criteria_artifact"]["path"],
        "protocol criteria",
        issues,
    )
    if criteria_path and criteria_path.is_file():
        actual_criteria_sha256 = hashlib.sha256(criteria_path.read_bytes()).hexdigest()
        if protocol["criteria_artifact"]["sha256"] != actual_criteria_sha256:
            issues.append("protocol criteria artifact hash is missing or stale")

    protocol_path = root / "01_protocol/protocol.json"
    if not protocol_path.is_file():
        issues.append("protocol.json is missing")
    else:
        actual_protocol_sha256 = hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        if actual_protocol_sha256 != action_input_sha256:
            issues.append("action input_sha256 does not match the current protocol.json")
    return issues
