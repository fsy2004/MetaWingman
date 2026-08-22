"""Post-lock scoring for blinded evidence-acquisition experiments."""

from __future__ import annotations

import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from .conclusion_directed_acquisition import CONFIGURATIONS


class ScoringError(ValueError):
    pass


_FROZEN_SEEDS = (20260820, 20260821, 20260822)


def validate_exact_receipt_slots(
    receipts: Iterable[dict[str, Any]],
    *,
    plan_id: str,
    case_id: str,
    corpus_sha256: str,
) -> None:
    """Bind post-lock scoring to the exact frozen 2x2-by-three-seed run."""
    rows = list(receipts)
    expected = {
        (configuration_id, seed)
        for configuration_id in CONFIGURATIONS
        for seed in _FROZEN_SEEDS
    }
    observed = {
        (row.get("configuration_id"), row.get("seed"))
        for row in rows
    }
    if len(rows) != len(expected) or len(observed) != len(rows) or observed != expected:
        raise ScoringError("receipts do not form the exact frozen Cartesian slot set")
    for row in rows:
        if (
            row.get("status") != "completed"
            or row.get("plan_id") != plan_id
            or row.get("case_id") != case_id
            or row.get("corpus_sha256") != corpus_sha256
        ):
            raise ScoringError("receipt identity, status, or corpus binding mismatch")


def validate_scoring_gate(plan: dict[str, Any], lock: dict[str, Any], *, expected_slots: int) -> None:
    expected = {
        "status": "locked",
        "plan_id": plan["plan_id"],
        "case_id": plan["case"]["case_id"],
        "corpus_sha256": plan["case"]["operational_corpus_sha256"],
        "locked_slots": expected_slots,
    }
    for key, value in expected.items():
        if lock.get(key) != value:
            raise ScoringError(f"scoring gate {key} mismatch")


def _surface(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _doi(value: Any) -> str:
    text = str(value or "").strip().casefold()
    match = re.search(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", text)
    return match.group(0).rstrip(".,;)]") if match else ""


def _pmid(value: Any) -> str:
    text = str(value or "")
    explicit = re.search(r"(?:pmid\s*[:#]?\s*)?(\d{7,8})\b", text, re.I)
    return explicit.group(1) if explicit else ""


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return 0
    value = 0
    for character in letters.group(0):
        value = value * 26 + ord(character) - 64
    return value - 1


def _xlsx_sheets(workbook_path) -> list[tuple[str, list[list[Any]]]]:
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(workbook_path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.itertext()) for node in root.findall(f"{{{main_ns}}}si")]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            node.attrib["Id"]: node.attrib["Target"]
            for node in relationships.findall(f"{{{package_ns}}}Relationship")
        }
        result = []
        for sheet in workbook.findall(f".//{{{main_ns}}}sheet"):
            target = targets[sheet.attrib[f"{{{rel_ns}}}id"]]
            path = str(PurePosixPath("xl") / target).replace("xl/../", "")
            root = ET.fromstring(archive.read(path))
            rows: list[list[Any]] = []
            for row in root.findall(f".//{{{main_ns}}}row"):
                values: list[Any] = []
                for cell in row.findall(f"{{{main_ns}}}c"):
                    column = _column_index(cell.attrib.get("r", "A1"))
                    while len(values) <= column:
                        values.append(None)
                    kind = cell.attrib.get("t")
                    value_node = cell.find(f"{{{main_ns}}}v")
                    inline = cell.find(f"{{{main_ns}}}is")
                    raw = value_node.text if value_node is not None else "".join(inline.itertext()) if inline is not None else ""
                    values[column] = shared[int(raw)] if kind == "s" and raw else raw
                rows.append(values)
            result.append((sheet.attrib.get("name", "sheet"), rows))
        return result


def extract_screening_reference_rows(
    rows: list[list[Any]],
) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Extract only expert-included records from a frozen screening snapshot."""
    if not rows:
        raise ScoringError("screening snapshot is empty")
    headers = {_surface(value): index for index, value in enumerate(rows[0]) if _surface(value)}
    required = {"title", "expert decision"}
    if not required.issubset(headers):
        raise ScoringError("screening snapshot lacks title or expert_decision")
    title_column = headers["title"]
    decision_column = headers["expert decision"]
    link_column = headers.get("link")
    extracted: list[dict[str, str]] = []
    audit = {
        "expert_included_rows": 0,
        "expert_excluded_rows": 0,
        "expert_unresolved_rows": 0,
    }
    for row in rows[1:]:
        decision = _surface(row[decision_column] if decision_column < len(row) else "")
        if decision == "include":
            audit["expert_included_rows"] += 1
            title = _surface(row[title_column] if title_column < len(row) else "")
            link = row[link_column] if link_column is not None and link_column < len(row) else ""
            if not title:
                raise ScoringError("expert-included screening row has no title")
            extracted.append({
                "doi": _doi(link),
                "pmid": _pmid(link),
                "title": title,
                "study": "",
            })
        elif decision == "exclude":
            audit["expert_excluded_rows"] += 1
        else:
            audit["expert_unresolved_rows"] += 1
    if not extracted:
        raise ScoringError("screening snapshot has no expert-included records")
    return extracted, audit


def extract_screening_workbook_reference(
    workbook_path,
    *,
    sheet_name: str = "Screening_snapshot",
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    sheets = dict(_xlsx_sheets(workbook_path))
    if sheet_name not in sheets:
        raise ScoringError(f"screening workbook lacks sheet: {sheet_name}")
    rows, audit = extract_screening_reference_rows(sheets[sheet_name])
    return rows, {"sheet": sheet_name, **audit}


def extract_reference_rows(workbook_path) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Extract study identity surfaces using a frozen header-driven rule."""
    extracted: list[dict[str, str]] = []
    sheets: list[dict[str, Any]] = []
    for sheet_name, rows in _xlsx_sheets(workbook_path):
        header_index = None
        columns: dict[int, str] = {}
        for index, row in enumerate(rows[:20]):
            candidate: dict[int, str] = {}
            for column, value in enumerate(row):
                header = _surface(value)
                if "doi" in header:
                    candidate[column] = "doi"
                elif "pmid" in header or "pubmed" in header:
                    candidate[column] = "pmid"
                elif "title" in header:
                    candidate[column] = "title"
                elif any(token in header for token in ("study id", "study identifier", "author", "reference", "citation", "publication")):
                    candidate[column] = "study"
            if candidate:
                header_index, columns = index, candidate
                break
        if header_index is None:
            sheets.append({"sheet": sheet_name, "status": "no_identity_header", "rows": 0})
            continue
        before = len(extracted)
        for row in rows[header_index + 1:]:
            identity = {"doi": "", "pmid": "", "title": "", "study": ""}
            for column, key in columns.items():
                value = row[column] if column < len(row) else None
                if value not in (None, ""):
                    identity[key] = (identity[key] + " " + str(value)).strip()
            combined = " ".join(identity.values())
            identity["doi"] = _doi(identity["doi"] or combined)
            identity["pmid"] = _pmid(identity["pmid"])
            identity["title"] = _surface(identity["title"])
            if identity["doi"] or identity["pmid"] or identity["title"]:
                extracted.append(identity)
        sheets.append({"sheet": sheet_name, "status": "parsed", "rows": len(extracted) - before, "header_row": header_index + 1})
    return extracted, {"sheets": sheets, "reference_rows": len(extracted)}


def match_reference_rows(
    reference_rows: Iterable[dict[str, str]], corpus: Iterable[dict[str, Any]]
) -> tuple[set[str], dict[str, Any]]:
    records = list(corpus)
    by_doi = {_doi(row.get("doi")): str(row["id"]) for row in records if _doi(row.get("doi"))}
    by_pmid = {str(row.get("pmid")): str(row["id"]) for row in records if row.get("pmid")}
    by_title = {_surface(row.get("title")): str(row["id"]) for row in records if _surface(row.get("title"))}
    matched: set[str] = set()
    rows = list(reference_rows)
    mapped_rows = 0
    methods = {"doi": 0, "pmid": 0, "title_exact": 0}
    for row in rows:
        record_id = None
        method = None
        reference_doi = _doi(row.get("doi"))
        reference_pmid = _pmid(row.get("pmid"))
        reference_title = _surface(row.get("title"))
        if reference_doi and reference_doi in by_doi:
            record_id, method = by_doi[reference_doi], "doi"
        elif reference_pmid and reference_pmid in by_pmid:
            record_id, method = by_pmid[reference_pmid], "pmid"
        elif reference_title and reference_title in by_title:
            record_id, method = by_title[reference_title], "title_exact"
        if record_id:
            mapped_rows += 1
            matched.add(record_id)
            methods[method] += 1
    return matched, {
        "reference_rows": len(rows), "mapped_rows": mapped_rows,
        "unique_mapped_corpus_records": len(matched), "mapping_methods": methods,
    }


def score_rankings(
    output: dict[str, Any], reference_ids: set[str], *, valid_corpus_ids: set[str],
    cutoffs: tuple[int, ...] = (50, 100, 200, 500, 1000),
) -> dict[str, Any]:
    if not reference_ids:
        raise ScoringError("no published reference identities mapped to the operational corpus")
    ranking = [str(value) for value in output.get("retrieval_candidate_ids", [])]
    selected = [str(value) for value in output.get("selected_candidate_ids", [])]
    result = {
        f"recall_at_{cutoff}": len(reference_ids.intersection(ranking[:cutoff])) / len(reference_ids)
        for cutoff in cutoffs
    }
    result.update({
        "mapped_reference_records": len(reference_ids),
        "selected_recall": len(reference_ids.intersection(selected)) / len(reference_ids),
        "selected_precision": len(reference_ids.intersection(selected)) / len(selected) if selected else 0.0,
        "invalid_selected_rate": sum(value not in valid_corpus_ids for value in selected) / len(selected) if selected else 0.0,
        "selected_count": len(selected),
    })
    return result


def _header_map(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    for index, row in enumerate(rows[:20]):
        headers = {_surface(value): column for column, value in enumerate(row) if _surface(value)}
        if any(key in headers for key in ("study id", "title")):
            return index, headers
    raise ScoringError("sheet has no study identity header")


def build_axis_reference_ids(
    sheets: list[tuple[str, list[list[Any]]]],
    corpus: Iterable[dict[str, Any]],
    axis_sheet_groups: dict[str, tuple[str, ...]],
) -> tuple[dict[str, set[str]], dict[str, Any]]:
    sheet_map = dict(sheets)
    if "References" not in sheet_map:
        raise ScoringError("workbook lacks a References sheet")
    reference_rows = sheet_map["References"]
    header_index, headers = _header_map(reference_rows)
    if "study id" not in headers or "title" not in headers:
        raise ScoringError("References sheet lacks Study ID or Title")
    by_title = {_surface(row.get("title")): str(row["id"]) for row in corpus if _surface(row.get("title"))}
    study_to_record: dict[str, str] = {}
    for row in reference_rows[header_index + 1:]:
        study_value = row[headers["study id"]] if headers["study id"] < len(row) else None
        title_value = row[headers["title"]] if headers["title"] < len(row) else None
        study_id, title = _surface(study_value), _surface(title_value)
        if study_id and title in by_title:
            study_to_record[study_id] = by_title[title]
    axes: dict[str, set[str]] = {}
    axis_audit: dict[str, Any] = {}
    for axis, sheet_names in axis_sheet_groups.items():
        study_ids: set[str] = set()
        for sheet_name in sheet_names:
            rows = sheet_map.get(sheet_name)
            if rows is None:
                raise ScoringError(f"axis sheet is missing: {sheet_name}")
            sheet_header, sheet_headers = _header_map(rows)
            if "study id" not in sheet_headers:
                raise ScoringError(f"axis sheet lacks Study ID: {sheet_name}")
            column = sheet_headers["study id"]
            for row in rows[sheet_header + 1:]:
                if column < len(row) and _surface(row[column]):
                    study_ids.add(_surface(row[column]))
        mapped = {study_to_record[value] for value in study_ids if value in study_to_record}
        axes[axis] = mapped
        axis_audit[axis] = {"workbook_study_ids": len(study_ids), "mapped_corpus_records": len(mapped), "sheets": list(sheet_names)}
    if any(not values for values in axes.values()):
        raise ScoringError("at least one conclusion axis has no mapped corpus records")
    return axes, {"reference_studies_linked_to_corpus": len(study_to_record), "mapped_reference_studies": len(set(study_to_record.values())), "axes": axis_audit}


def score_axis_coverage(
    output: dict[str, Any], axes: dict[str, set[str]], *, cutoffs: tuple[int, ...] = (50, 100, 200, 500, 1000)
) -> dict[str, Any]:
    ranking = [str(value) for value in output.get("retrieval_candidate_ids", [])]
    if not axes or any(not values for values in axes.values()):
        raise ScoringError("axis scoring requires non-empty registered axes")
    result: dict[str, Any] = {"axis_count": len(axes)}
    for cutoff in cutoffs:
        recalls = {axis: len(values.intersection(ranking[:cutoff])) / len(values) for axis, values in axes.items()}
        result[f"axis_macro_recall_at_{cutoff}"] = sum(recalls.values()) / len(recalls)
        result[f"axes_with_any_at_{cutoff}"] = sum(value > 0 for value in recalls.values()) / len(recalls)
        result[f"axis_recalls_at_{cutoff}"] = recalls
    return result
