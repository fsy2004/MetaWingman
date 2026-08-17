"""Reproducible, source-anchored training-corpus primitives."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

from .network_security import PublicNetworkError, public_https_opener, validate_public_https_url
from .schema_guard import validate_document
from .state_store import atomic_write_json, canonical_json


class TrainingCorpusError(ValueError):
    """Raised when a training-corpus action is unsafe or irreproducible."""


DEFAULT_LICENSES = ("cc by", "cc by-nc", "cc by-nc-nd", "cc by-nc-sa", "cc0")
ROLE_PATTERNS = (
    ("search", re.compile(r"\b(search|information source|database|electronic source)\b", re.I)),
    ("eligibility", re.compile(r"\b(eligib|inclusion|exclusion|selection criteria|study criteria)\b", re.I)),
    ("selection", re.compile(r"\b(study selection|screening|record selection)\b", re.I)),
    ("extraction", re.compile(r"\b(data extraction|data collection|data abstraction)\b", re.I)),
    ("appraisal", re.compile(r"\b(risk of bias|quality assessment|critical appraisal)\b", re.I)),
    ("synthesis", re.compile(r"\b(meta-analysis|statistical analysis|data synthesis|evidence synthesis)\b", re.I)),
    ("certainty", re.compile(r"\b(certainty|grade|strength of evidence)\b", re.I)),
    ("protocol", re.compile(r"\b(protocol|registration|prospero)\b", re.I)),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_license(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _family_split(family_id: str, seed: int, train_fraction: float) -> str:
    digest = hashlib.sha256(f"{seed}:{family_id}".encode("utf-8")).digest()
    fraction = int.from_bytes(digest[:8], "big") / float(2**64)
    return "train" if fraction < train_fraction else "development"


def _stable_record_key(record: dict[str, Any], seed: int) -> str:
    return hashlib.sha256(f"{seed}:{record['record_id']}".encode("utf-8")).hexdigest()


_QUESTION_TERMS = (
    ("harms", ("adverse events", "adverse event", "adverse effects", "adverse effect", "safety", "harm", "toxicity")),
    ("diagnostic", ("diagnostic", "sensitivity", "specificity", "screening test")),
    ("prognostic", ("prognostic", "prognosis", "survival prediction")),
    ("prevalence", ("prevalence", "incidence", "burden")),
    ("etiology", ("risk factor", "association", "etiology", "aetiology")),
    ("intervention", ("intervention", "treatment", "therapy", "immunotherapy", "prevention")),
)


def _source_phrase_matches(text: str, terms: Iterable[str]) -> list[str]:
    lower = text.casefold()
    matches: list[str] = []
    for term in sorted(set(terms), key=lambda value: (-len(value), value)):
        match = re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", lower)
        if match:
            matches.append(text[match.start() : match.end()])
    return matches


def classify_biomedical_stratum(record: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Create an evidence-bearing weak stratum from title/publication types only."""
    title = str(record.get("title") or "")
    publication_types = [str(item) for item in record.get("publication_types", []) if str(item)]
    source = " ".join([title, *publication_types]).strip()
    specialty_hits: list[tuple[int, str, str]] = []
    evidence: list[str] = []
    for specialty in registry.get("specialties", []):
        terms = [*specialty.get("title_terms", []), *specialty.get("aliases", [])]
        matches = _source_phrase_matches(source, terms)
        if matches:
            specialty_hits.append((max(len(item) for item in matches), specialty["specialty_id"], matches[0]))
    specialty_hits.sort(key=lambda item: (-item[0], item[1], item[2].casefold()))
    specialty_ids = list(dict.fromkeys(item[1] for item in specialty_hits))
    primary_specialty = specialty_ids[0] if specialty_ids else "general-medicine"
    secondary_specialties = specialty_ids[1:]
    evidence.extend(f"title_or_publication_type:{item[2]}=>specialty:{item[1]}" for item in specialty_hits)

    question_type = "unresolved"
    for candidate, terms in _QUESTION_TERMS:
        matches = _source_phrase_matches(source, terms)
        if matches:
            question_type = candidate
            evidence.append(f"title_or_publication_type:{matches[0]}=>question_type:{candidate}")
            break
    normalized_designs = sorted(
        {
            re.sub(r"[^a-z0-9]+", "_", item.casefold()).strip("_")
            for item in publication_types
            if re.sub(r"[^a-z0-9]+", "_", item.casefold()).strip("_")
        }
    ) or ["unresolved"]
    if publication_types:
        evidence.extend(f"publication_type:{item}" for item in publication_types)
    synthesis_route = "pairwise"
    if re.search(r"\bnetwork meta-analysis\b", title, flags=re.IGNORECASE):
        synthesis_route = "network"
        evidence.append("title:network meta-analysis=>synthesis_route:network")
    elif question_type == "diagnostic" and re.search(r"\b(meta-analysis|systematic review)\b", title, flags=re.IGNORECASE):
        synthesis_route = "diagnostic"
        evidence.append("title:diagnostic review=>synthesis_route:diagnostic")
    else:
        evidence.append("default:synthesis_route:pairwise")
    challenge_tags = []
    if len(specialty_ids) > 1:
        challenge_tags.append("cross_specialty")
    if question_type == "harms":
        challenge_tags.append("adverse_event_evidence")
    if not specialty_hits:
        evidence.append("fallback:no_specialty_term_match=>general-medicine")
    if question_type == "unresolved":
        evidence.append("fallback:no_question_term_match=>unresolved")
    sampling_key = "|".join((primary_specialty, question_type, normalized_designs[0], synthesis_route))
    stratum = {
        "schema_version": "1.0",
        "primary_specialty": primary_specialty,
        "secondary_specialties": secondary_specialties,
        "question_type": question_type,
        "study_designs": normalized_designs,
        "synthesis_routes": [synthesis_route],
        "languages": ["en"],
        "document_modalities": ["metadata", "abstract"],
        "challenge_tags": challenge_tags,
        "sampling_key": sampling_key,
        "label_status": "deterministic_weak_candidate",
        "evidence": list(dict.fromkeys(evidence)),
    }
    validate_document(stratum, "biomedical_training_stratum")
    return stratum


def build_training_plan(
    corpus: dict[str, Any], families: dict[str, Any], *, plan_id: str,
    source_corpus_path: str, source_corpus_sha256: str,
    family_registry_path: str, family_registry_sha256: str,
    maximum_records: int = 24, seed: int = 20260815,
    train_fraction: float = 0.8, allowed_licenses: Iterable[str] = DEFAULT_LICENSES,
    created_at_utc: str | None = None,
    specialty_registry: dict[str, Any] | None = None,
    specialty_registry_path: str | None = None,
    specialty_registry_sha256: str | None = None,
) -> dict[str, Any]:
    if maximum_records < 1 or not 0 < train_fraction < 1:
        raise TrainingCorpusError("maximum_records and train_fraction are invalid")
    allowed = sorted({_normalise_license(item) for item in allowed_licenses if item.strip()})
    if not allowed:
        raise TrainingCorpusError("at least one allowed license is required")

    record_to_family: dict[str, dict[str, Any]] = {}
    for family in families.get("families", []):
        if family.get("status") in {"blocked_integrity", "excluded_non_reference"}:
            continue
        for record_id in family.get("record_ids", []):
            if record_id in record_to_family:
                raise TrainingCorpusError(f"record belongs to multiple families: {record_id}")
            record_to_family[record_id] = family

    eligible: list[dict[str, Any]] = []
    for record in corpus.get("records", []):
        family = record_to_family.get(record.get("record_id"))
        if not family:
            continue
        if record.get("admission_status") != "development_candidate":
            continue
        if record.get("integrity_status") != "no_status_update_in_epmc_record":
            continue
        if not record.get("is_open_access") or not record.get("pmcid"):
            continue
        if _normalise_license(str(record.get("license") or "")) not in allowed:
            continue
        candidate = {**record, "_family_id": family["family_id"]}
        if specialty_registry is not None:
            candidate["_biomedical_stratum"] = classify_biomedical_stratum(record, specialty_registry)
        eligible.append(candidate)

    selected: list[dict[str, Any]] = []
    if specialty_registry is None:
        by_journal: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in eligible:
            by_journal[record["journal"]].append(record)
        for records in by_journal.values():
            records.sort(key=lambda item: _stable_record_key(item, seed))
        journals = sorted(by_journal, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
        while len(selected) < maximum_records:
            added = False
            for journal in journals:
                if by_journal[journal] and len(selected) < maximum_records:
                    selected.append(by_journal[journal].pop(0))
                    added = True
            if not added:
                break
    else:
        if not specialty_registry_path or not specialty_registry_sha256:
            raise TrainingCorpusError("biomedical planning requires specialty registry path and sha256")
        by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in eligible:
            by_stratum[record["_biomedical_stratum"]["sampling_key"]].append(record)
        for records in by_stratum.values():
            records.sort(key=lambda item: _stable_record_key(item, seed))
        stratum_keys = sorted(by_stratum, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
        while len(selected) < maximum_records:
            added = False
            for sampling_key in stratum_keys:
                if by_stratum[sampling_key] and len(selected) < maximum_records:
                    selected.append(by_stratum[sampling_key].pop(0))
                    added = True
            if not added:
                break

    output_records = []
    for record in selected:
        split = _family_split(record["_family_id"], seed, train_fraction)
        output_record = {
            "record_id": record["record_id"],
            "family_id": record["_family_id"],
            "split": split,
            "split_status": "provisional_family_isolated_not_held_out",
            "title": record["title"],
            "year": record["year"],
            "journal": record["journal"],
            "journal_stratum": record["journal_stratum"],
            "doi": record.get("doi", ""),
            "pmid": record.get("pmid", ""),
            "pmcid": record["pmcid"],
            "declared_license": _normalise_license(record["license"]),
            "source_url": record["source_url"],
            "integrity_status": record["integrity_status"],
        }
        if specialty_registry is not None:
            output_record["biomedical_stratum"] = record["_biomedical_stratum"]
        output_records.append(output_record)
    output_records.sort(key=lambda item: (item["split"], item["family_id"], item["record_id"]))
    split_counts = Counter(item["split"] for item in output_records)
    schema_version = "1.1" if specialty_registry is not None else "1.0"
    inputs = {
        "source_corpus_path": source_corpus_path,
        "source_corpus_sha256": source_corpus_sha256,
        "family_registry_path": family_registry_path,
        "family_registry_sha256": family_registry_sha256,
    }
    if specialty_registry is not None:
        inputs.update({
            "specialty_registry_path": specialty_registry_path,
            "specialty_registry_sha256": specialty_registry_sha256,
        })
    plan = {
        "schema_version": schema_version,
        "plan_id": plan_id,
        "created_at_utc": created_at_utc or utc_now(),
        "inputs": inputs,
        "policy": {
            "seed": seed,
            "maximum_records": maximum_records,
            "train_fraction": train_fraction,
            "split_policy": "review_family_hash_train_development_only",
            "held_out_enabled": False,
            "journal_is_stratum_not_oracle": True,
            "require_open_access": True,
            "require_pmcid": True,
            "allowed_licenses": allowed,
            "label_policy": "source_anchored_weak_supervision_until_independently_verified",
        },
        "summary": {
            "eligible_records": len(eligible),
            "selected_records": len(output_records),
            "train_records": split_counts["train"],
            "development_records": split_counts["development"],
            "selected_families": len({item["family_id"] for item in output_records}),
            "selected_journals": len({item["journal"] for item in output_records}),
        },
    }
    if specialty_registry is not None:
        strata = [item["biomedical_stratum"] for item in output_records]
        plan["domain_policy"] = {
            "application_domain": "human_health_clinical_translational_biomedicine",
            "classifier_version": "biomedical-title-terms-v1",
            "source_fields": ["title", "publication_types"],
            "journal_feature_forbidden": True,
            "label_status": "deterministic_weak_candidate",
        }
        plan["strata_summary"] = {
            "sampling_keys": dict(sorted(Counter(item["sampling_key"] for item in strata).items())),
            "primary_specialties": dict(sorted(Counter(item["primary_specialty"] for item in strata).items())),
            "question_types": dict(sorted(Counter(item["question_type"] for item in strata).items())),
        }
    plan["records"] = output_records
    validate_document(plan, "training_corpus_plan")
    return plan


def _safe_destination(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise TrainingCorpusError(f"unsafe training artifact destination: {relative}")
    destination = (root / Path(*posix.parts)).resolve()
    try:
        destination.relative_to(root.resolve())
    except ValueError as exc:
        raise TrainingCorpusError(f"training artifact escapes output root: {relative}") from exc
    return destination


def _request_bytes(
    url: str, *, max_bytes: int, attempts: int = 3, deadline_seconds: float = 120.0,
) -> tuple[bytes, str]:
    try:
        safe_url = validate_public_https_url(url)
    except PublicNetworkError as exc:
        raise TrainingCorpusError(f"unsafe training source URL: {exc}") from exc
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(safe_url, headers={"User-Agent": "MetaWingman-training-corpus/1.0"})
        try:
            with public_https_opener().open(request, timeout=60) as response:
                final_url = validate_public_https_url(response.geturl())
                chunks: list[bytes] = []
                total = 0
                deadline = time.monotonic() + deadline_seconds
                while True:
                    if time.monotonic() > deadline:
                        raise TrainingCorpusError(
                            f"download exceeded wall-clock deadline: {deadline_seconds}s"
                        )
                    chunk = response.read(min(1024 * 1024, max_bytes + 1 - total))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        raise TrainingCorpusError(f"download exceeds per-file byte limit: {max_bytes}")
                return b"".join(chunks), final_url
        except (OSError, urllib.error.URLError, PublicNetworkError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise TrainingCorpusError(f"training source retrieval failed: {last_error}")


def _json_api(url: str, max_bytes: int = 5 * 1024 * 1024, deadline_seconds: float = 120.0) -> dict[str, Any]:
    body, _ = _request_bytes(url, max_bytes=max_bytes, deadline_seconds=deadline_seconds)
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingCorpusError(f"invalid JSON response from training source: {exc}") from exc
    if not isinstance(value, dict):
        raise TrainingCorpusError("training source JSON response is not an object")
    return value


def _oa_license(pmcid: str, deadline_seconds: float = 120.0) -> tuple[str | None, str]:
    url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=" + urllib.parse.quote(pmcid)
    body, _ = _request_bytes(url, max_bytes=2 * 1024 * 1024, deadline_seconds=deadline_seconds)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise TrainingCorpusError(f"invalid PMC OA license response: {exc}") from exc
    record = root.find("./records/record")
    if record is None:
        return None, "unverified"
    if str(record.attrib.get("retracted", "")).casefold() == "yes":
        return record.attrib.get("license"), "rejected_retracted"
    return record.attrib.get("license"), "verified_not_retracted"


def _full_text_urls(record: dict[str, Any], deadline_seconds: float = 120.0) -> tuple[str | None, str]:
    query = f"EXT_ID:{record['pmid']} AND SRC:MED" if record.get("pmid") else f"PMC_ID:{record['pmcid']}"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({
        "query": query, "format": "json", "resultType": "core", "pageSize": 1,
    })
    payload = _json_api(url, deadline_seconds=deadline_seconds)
    results = payload.get("resultList", {}).get("result", [])
    if not results:
        raise TrainingCorpusError("Europe PMC core record was not found")
    pdf_url = None
    for item in results[0].get("fullTextUrlList", {}).get("fullTextUrl", []):
        if item.get("availabilityCode") == "OA" and item.get("documentStyle") == "pdf":
            pdf_url = item.get("url")
            break
    xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{record['pmcid']}/fullTextXML"
    return pdf_url, xml_url


def _write_atomic(destination: Path, body: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, destination)
    except Exception:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parser_metrics(pdf_path: Path | None, xml_path: Path | None) -> dict[str, int]:
    metrics = {
        "pdf_pages": 0, "native_text_characters": 0, "pages_without_native_text": 0,
        "image_blocks": 0, "rotated_pages": 0, "jats_characters": 0,
        "jats_sections": 0, "jats_tables": 0, "jats_figures": 0, "jats_references": 0,
    }
    if pdf_path is not None:
        try:
            import fitz
            pdf = fitz.open(pdf_path)
            try:
                metrics["pdf_pages"] = pdf.page_count
                for page in pdf:
                    text = page.get_text("text")
                    metrics["native_text_characters"] += len(text.strip())
                    metrics["pages_without_native_text"] += int(not text.strip())
                    metrics["rotated_pages"] += int(bool(page.rotation))
                    metrics["image_blocks"] += sum(
                        1 for block in page.get_text("dict").get("blocks", []) if block.get("type") == 1
                    )
            finally:
                pdf.close()
        except Exception as exc:
            raise TrainingCorpusError(f"PDF parser failed: {exc}") from exc
    if xml_path is not None:
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError as exc:
            raise TrainingCorpusError(f"JATS parser failed: {exc}") from exc
        metrics["jats_characters"] = len(" ".join(part.strip() for part in root.itertext() if part.strip()))
        counts = Counter(_local_name(item.tag) for item in root.iter())
        metrics["jats_sections"] = counts["sec"]
        metrics["jats_tables"] = counts["table-wrap"]
        metrics["jats_figures"] = counts["fig"]
        metrics["jats_references"] = counts["ref"]
    return metrics


def _artifact(kind: str, source_url: str, path: Path, root: Path, media_type: str) -> dict[str, Any]:
    return {
        "kind": kind, "source_url": source_url,
        "relative_path": path.relative_to(root).as_posix(), "media_type": media_type,
        "bytes": path.stat().st_size, "sha256": sha256_file(path),
    }


def _reusable_documents(output_root: Path, plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest_path = output_root / "training-document-manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_document(manifest, "training_document_manifest")
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if manifest["plan_id"] != plan["plan_id"] or manifest["plan_sha256"] != hashlib.sha256(canonical_json(plan)).hexdigest():
        return {}
    planned = {item["record_id"]: item for item in plan["records"]}
    reusable: dict[str, dict[str, Any]] = {}
    for document in manifest["documents"]:
        record = planned.get(document["record_id"])
        if record is None or document["retrieval_status"] == "failed":
            continue
        if document["family_id"] != record["family_id"] or document["split"] != record["split"]:
            continue
        valid = True
        for artifact in document["artifacts"]:
            try:
                path = _safe_destination(output_root, artifact["relative_path"])
            except TrainingCorpusError:
                valid = False
                break
            if not path.is_file() or path.stat().st_size != artifact["bytes"] or sha256_file(path) != artifact["sha256"]:
                valid = False
                break
        if valid:
            reusable[document["record_id"]] = document
    return reusable


def fetch_training_plan(
    plan: dict[str, Any], output_root: Path, *, manifest_id: str,
    maximum_records: int | None = None, max_file_bytes: int = 40 * 1024 * 1024,
    max_total_bytes: int = 500 * 1024 * 1024, delay_seconds: float = 0.2,
    created_at_utc: str | None = None, reuse_existing: bool = True,
    skip_pdf: bool = False, request_deadline_seconds: float = 120.0,
) -> dict[str, Any]:
    validate_document(plan, "training_corpus_plan")
    output_root = output_root.resolve()
    documents: list[dict[str, Any]] = []
    total_bytes = 0
    records = plan["records"][:maximum_records] if maximum_records else plan["records"]
    allowed = set(plan["policy"]["allowed_licenses"])
    reusable = _reusable_documents(output_root, plan) if reuse_existing else {}
    for record in records:
        if record["record_id"] in reusable:
            document = reusable[record["record_id"]]
            document_bytes = sum(item["bytes"] for item in document["artifacts"])
            if total_bytes + document_bytes > max_total_bytes:
                raise TrainingCorpusError(f"training corpus exceeds total byte limit: {max_total_bytes}")
            documents.append(document)
            total_bytes += document_bytes
            continue
        failures: list[str] = []
        artifacts: list[dict[str, Any]] = []
        pdf_path: Path | None = None
        xml_path: Path | None = None
        integrity_status = "unverified"
        retrieved_license = record["declared_license"]
        pdf_url: str | None = None
        xml_url: str | None = None
        base = f"{record['split']}/{record['family_id'].replace(':', '-')}/{record['pmcid']}"
        try:
            api_license, integrity_status = _oa_license(record["pmcid"], deadline_seconds=request_deadline_seconds)
            if api_license:
                retrieved_license = _normalise_license(api_license)
            if integrity_status == "rejected_retracted":
                raise TrainingCorpusError("PMC OA service marks the article as retracted")
            if retrieved_license not in allowed:
                raise TrainingCorpusError(f"article license is outside the frozen allowlist: {retrieved_license}")
            if skip_pdf:
                xml_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{record['pmcid']}/fullTextXML"
            else:
                pdf_url, xml_url = _full_text_urls(record, deadline_seconds=request_deadline_seconds)
        except TrainingCorpusError as exc:
            failures.append(str(exc))

        if not skip_pdf and not failures and pdf_url:
            try:
                body, final_url = _request_bytes(pdf_url, max_bytes=max_file_bytes, deadline_seconds=request_deadline_seconds)
                if not body.startswith(b"%PDF"):
                    failures.append("pdf_endpoint_did_not_return_pdf")
                else:
                    if total_bytes + len(body) > max_total_bytes:
                        raise TrainingCorpusError(f"training corpus exceeds total byte limit: {max_total_bytes}")
                    pdf_path = _safe_destination(output_root, base + ".pdf")
                    _write_atomic(pdf_path, body)
                    artifacts.append(_artifact("pdf", final_url, pdf_path, output_root, "application/pdf"))
                    total_bytes += len(body)
            except TrainingCorpusError as exc:
                failures.append(f"pdf_retrieval_failed: {exc}")
        elif not skip_pdf and not failures:
            failures.append("no_open_access_pdf_url")

        if xml_url is not None and integrity_status == "verified_not_retracted" and retrieved_license in allowed:
            try:
                body, final_url = _request_bytes(xml_url, max_bytes=max_file_bytes, deadline_seconds=request_deadline_seconds)
                try:
                    ET.fromstring(body)
                except ET.ParseError as exc:
                    raise TrainingCorpusError(f"fullTextXML endpoint returned invalid XML: {exc}") from exc
                if total_bytes + len(body) > max_total_bytes:
                    raise TrainingCorpusError(f"training corpus exceeds total byte limit: {max_total_bytes}")
                xml_path = _safe_destination(output_root, base + ".xml")
                _write_atomic(xml_path, body)
                artifacts.append(_artifact("jats_xml", final_url, xml_path, output_root, "application/xml"))
                total_bytes += len(body)
            except TrainingCorpusError as exc:
                failures.append(f"xml_retrieval_failed: {exc}")

        try:
            metrics = _parser_metrics(pdf_path, xml_path)
        except TrainingCorpusError as exc:
            failures.append(f"parser_failed: {exc}")
            metrics = _parser_metrics(None, None)
        if skip_pdf:
            status = (
                "complete" if xml_path is not None and not failures
                else ("partial" if xml_path is not None else "failed")
            )
        else:
            status = "complete" if {item["kind"] for item in artifacts} == {"pdf", "jats_xml"} and not failures else ("partial" if artifacts else "failed")
        documents.append({
            "document_id": f"training-document:{record['pmcid']}",
            "record_id": record["record_id"], "family_id": record["family_id"],
            "split": record["split"], "pmcid": record["pmcid"], "title": record["title"],
            "license": retrieved_license, "integrity_status": integrity_status,
            "retrieval_status": status, "failure_reasons": sorted(set(failures)),
            "artifacts": artifacts, "parser_metrics": metrics,
            "label_status": "source_document_only_not_gold",
        })
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    statuses = Counter(item["retrieval_status"] for item in documents)
    artifact_kinds = Counter(a["kind"] for item in documents for a in item["artifacts"])
    manifest = {
        "schema_version": "1.0", "manifest_id": manifest_id,
        "created_at_utc": created_at_utc or utc_now(), "plan_id": plan["plan_id"],
        "plan_sha256": hashlib.sha256(canonical_json(plan)).hexdigest(),
        "source_policy": {
            "metadata_api": "Europe PMC REST", "full_text_api": "Europe PMC OA",
            "license_api": "PMC OA Web Service", "public_https_only": True,
            "article_level_license_required": True, "retractions_rejected": True,
        },
        "summary": {
            "planned": len(records), "complete": statuses["complete"], "partial": statuses["partial"],
            "failed": statuses["failed"], "pdf_files": artifact_kinds["pdf"],
            "xml_files": artifact_kinds["jats_xml"], "total_bytes": total_bytes,
        },
        "documents": documents,
    }
    validate_document(manifest, "training_document_manifest")
    atomic_write_json(output_root / "training-document-manifest.json", manifest, "training_document_manifest")
    return manifest


def _section_role(title: str) -> str | None:
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(title):
            return role
    return None


def _direct_section_text(section: ET.Element) -> str:
    parts: list[str] = []
    for child in section:
        name = _local_name(child.tag)
        if name in {"title", "sec"}:
            continue
        parts.extend(value.strip() for value in child.itertext() if value.strip())
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def build_training_examples(
    manifest: dict[str, Any], artifact_root: Path, *, maximum_characters: int = 8000,
    minimum_characters: int = 200,
) -> list[dict[str, Any]]:
    validate_document(manifest, "training_document_manifest")
    examples: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    family_splits: dict[str, set[str]] = defaultdict(set)
    for document in manifest["documents"]:
        family_splits[document["family_id"]].add(document["split"])
    conflicts = sorted(family for family, splits in family_splits.items() if len(splits) > 1)
    if conflicts:
        raise TrainingCorpusError(f"review families cross training splits: {', '.join(conflicts)}")
    for document in manifest["documents"]:
        xml_artifact = next((item for item in document["artifacts"] if item["kind"] == "jats_xml"), None)
        if not xml_artifact or document["integrity_status"] != "verified_not_retracted":
            continue
        xml_path = _safe_destination(artifact_root.resolve(), xml_artifact["relative_path"])
        if not xml_path.is_file():
            raise TrainingCorpusError(f"training XML artifact is missing: {xml_artifact['relative_path']}")
        if xml_path.stat().st_size != xml_artifact["bytes"] or sha256_file(xml_path) != xml_artifact["sha256"]:
            raise TrainingCorpusError(f"training XML artifact hash or size drift: {xml_artifact['relative_path']}")
        root = ET.parse(xml_path).getroot()
        index = 0
        for section in (item for item in root.iter() if _local_name(item.tag) == "sec"):
            index += 1
            title_element = next((item for item in section if _local_name(item.tag) == "title"), None)
            title = " ".join(title_element.itertext()).strip() if title_element is not None else ""
            role = _section_role(title)
            text = _direct_section_text(section)
            if role is None or len(text) < minimum_characters:
                continue
            text = text[:maximum_characters]
            source_text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            for task, instruction in (
                ("section_role_classification", "Classify this source passage into the systematic-review workflow role."),
                ("evidence_retrieval", f"Identify the source passage that supports the review workflow field: {role}."),
            ):
                identity = f"{document['document_id']}:{index}:{task}:{source_text_sha}"
                example_id = "example:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
                if example_id in seen_ids:
                    raise TrainingCorpusError(f"duplicate training example id: {example_id}")
                example = {
                    "schema_version": "1.0", "example_id": example_id,
                    "document_id": document["document_id"], "record_id": document["record_id"],
                    "family_id": document["family_id"], "split": document["split"], "task": task,
                    "instruction": instruction, "review_title": document.get("title", ""),
                    "input_text": f"Section title: {title}\n\n{text}",
                    "target": {"section_role": role, "section_title": title},
                    "evidence_anchor": {
                        "artifact_sha256": xml_artifact["sha256"], "section_path": f"//body//sec[{index}]",
                        "section_index": index, "source_text_sha256": source_text_sha,
                    },
                    "label_status": "deterministic_weak_supervision_requires_independent_validation",
                    "gold_label": False,
                }
                example["content_sha256"] = hashlib.sha256(canonical_json({k: v for k, v in example.items() if k != "content_sha256"})).hexdigest()
                validate_document(example, "training_example")
                examples.append(example)
                seen_ids.add(example_id)
    examples.sort(key=lambda item: item["example_id"])
    return examples


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _retrieval_query(example: dict[str, Any]) -> str:
    """Query text for the evidence-retrieval task.

    Includes the review title so the query identifies which review is being
    asked about; the field-only instruction alone is not a well-posed
    full-corpus query (many passages from different reviews support the same
    field).
    """
    title = example.get("review_title") or ""
    if title:
        return f"{example['instruction']} Review: {title}"
    return example["instruction"]


def _build_token_matrix(
    retrieval: list[dict[str, Any]],
    document_token_sets: dict[str, set[str]],
) -> tuple[Any, dict[str, int], dict[str, int]] | None:
    """Build the sparse document-token binary matrix used for vectorized overlap.

    Row ``i`` corresponds to ``retrieval[i]`` and holds a 1 in every column
    whose token is present in that document's token set. Returns ``None`` when
    numpy/scipy are unavailable so callers can fall back to pure Python. The
    matrix data is accumulated in int32 (never int8) so overlap counts, which
    are bounded by the token-set sizes, cannot overflow.
    """
    try:
        import numpy as np
        from scipy import sparse
    except ImportError:
        return None

    positions = {item["example_id"]: index for index, item in enumerate(retrieval)}
    vocabulary: dict[str, int] = {}
    rows: list[int] = []
    columns: list[int] = []
    for row, item in enumerate(retrieval):
        for token in document_token_sets[item["example_id"]]:
            column = vocabulary.setdefault(token, len(vocabulary))
            rows.append(row)
            columns.append(column)
    matrix = sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.int32), (rows, columns)),
        shape=(len(retrieval), len(vocabulary)),
    )
    token_columns = {token: column for token, column in vocabulary.items()}
    return matrix, token_columns, positions


def _build_overlap_lookup(
    retrieval: list[dict[str, Any]],
    document_token_sets: dict[str, set[str]],
) -> Callable[[set[str], list[str]], dict[str, int]]:
    """Token-overlap lookup: batched sparse matrix-vector when scipy is available.

    The vectorized path computes identical overlap values (binary token set
    intersection sizes) and falls back to the pure-Python loop otherwise.
    """

    def python_lookup(query_tokens: set[str], candidate_ids: list[str]) -> dict[str, int]:
        return {
            identifier: len(query_tokens & document_token_sets[identifier])
            for identifier in candidate_ids
        }

    try:
        import numpy as np
    except ImportError:
        return python_lookup

    built = _build_token_matrix(retrieval, document_token_sets)
    if built is None:
        return python_lookup
    matrix, token_columns, positions = built

    def sparse_lookup(query_tokens: set[str], candidate_ids: list[str]) -> dict[str, int]:
        indices = np.asarray([positions[identifier] for identifier in candidate_ids], dtype=np.int64)
        query_columns = np.asarray(
            [token_columns[token] for token in query_tokens if token in token_columns],
            dtype=np.int64,
        )
        if query_columns.size == 0:
            overlaps = np.zeros(len(candidate_ids), dtype=np.int64)
        else:
            query_vector = np.zeros(len(token_columns), dtype=np.int32)
            query_vector[query_columns] = 1
            overlaps = np.asarray(matrix[indices] @ query_vector, dtype=np.int64).ravel()
        return {
            identifier: int(value)
            for identifier, value in zip(candidate_ids, overlaps.tolist())
        }

    return sparse_lookup


def _pair_tie(seed: int, query_id: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed}:{query_id}:{candidate_id}".encode()).hexdigest()


def _python_negative_selector(
    retrieval: list[dict[str, Any]],
    strata_by_record: dict[str, dict[str, Any]],
    seed: int,
    query_token_sets: dict[str, set[str]],
    document_token_sets: dict[str, set[str]],
) -> Callable[[dict[str, Any]], list[tuple[dict[str, Any], int, list[str]]]]:
    """Original per-query Python selection, kept as the no-scipy fallback."""
    by_specialty: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in retrieval:
        stratum = strata_by_record.get(item["record_id"])
        if not stratum:
            continue
        by_specialty[stratum.get("primary_specialty")].append(item)
        by_question[stratum.get("question_type")].append(item)
    overlap_lookup = _build_overlap_lookup(retrieval, document_token_sets)

    def select(query: dict[str, Any]) -> list[tuple[dict[str, Any], int, list[str]]]:
        query_stratum = strata_by_record.get(query["record_id"])
        query_tokens = query_token_sets[query["example_id"]]
        neighborhood: dict[str, dict[str, Any]] = {}
        for candidate in by_specialty.get(query_stratum.get("primary_specialty"), []):
            neighborhood[candidate["example_id"]] = candidate
        for candidate in by_question.get(query_stratum.get("question_type"), []):
            neighborhood[candidate["example_id"]] = candidate
        overlap_map = overlap_lookup(query_tokens, list(neighborhood))
        candidates: list[tuple[int, str, dict[str, Any], list[str]]] = []
        for candidate in neighborhood.values():
            if candidate["split"] != query["split"]:
                continue
            if candidate["record_id"] == query["record_id"] or candidate["family_id"] == query["family_id"]:
                continue
            if candidate["input_text"] == query["input_text"]:
                continue
            if candidate["evidence_anchor"]["source_text_sha256"] == query["evidence_anchor"]["source_text_sha256"]:
                continue
            candidate_stratum = strata_by_record.get(candidate["record_id"])
            if not candidate_stratum:
                continue
            neighborhood_keys = []
            if candidate_stratum["primary_specialty"] == query_stratum["primary_specialty"]:
                neighborhood_keys.append("primary_specialty")
            if candidate_stratum["question_type"] == query_stratum["question_type"]:
                neighborhood_keys.append("question_type")
            overlap = overlap_map[candidate["example_id"]]
            tie = _pair_tie(seed, query["example_id"], candidate["example_id"])
            candidates.append((-overlap, tie, candidate, neighborhood_keys))
        return [(item[2], 0, item[3]) for item in sorted(candidates)[:3]]

    return select


def _vectorized_negative_selector(
    retrieval: list[dict[str, Any]],
    strata_by_record: dict[str, dict[str, Any]],
    seed: int,
    query_token_sets: dict[str, set[str]],
    matrix: Any,
    token_columns: dict[str, int],
) -> Callable[[dict[str, Any]], list[tuple[dict[str, Any], int, list[str]]]]:
    """Batch per-query candidate filtering with numpy/scipy.

    Replaces the per-query Python loop over the medical neighborhood with a
    boolean-mask filter over precomputed code arrays, then ranks the passing
    candidates by token overlap. Overlaps are computed with a sparse
    matrix-vector product per query: the document-token matrix is sliced once
    per (specialty, question) neighborhood and the query vector is reused
    across queries, avoiding per-candidate Python work and per-query sparse
    fancy indexing. The sha256 tie-break is only computed for candidates tied
    at the third-ranked overlap (the selection boundary), which is the one
    place the tie affects which three negatives are chosen; this keeps output
    byte-identical while avoiding a sha256 per passing candidate.
    """
    import numpy as np

    n = len(retrieval)
    example_ids = [item["example_id"] for item in retrieval]

    split = np.empty(n, dtype=np.int64)
    rec = np.empty(n, dtype=np.int64)
    fam = np.empty(n, dtype=np.int64)
    intext = np.empty(n, dtype=np.int64)
    srcsha = np.empty(n, dtype=np.int64)
    spec = np.empty(n, dtype=np.int64)
    qtype = np.empty(n, dtype=np.int64)
    has_stratum = np.zeros(n, dtype=bool)

    split_codes: dict[str, int] = {}
    rec_codes: dict[str, int] = {}
    fam_codes: dict[str, int] = {}
    intext_codes: dict[str, int] = {}
    srcsha_codes: dict[str, int] = {}
    spec_codes: dict[str, int] = {}
    qtype_codes: dict[str, int] = {}

    for i, item in enumerate(retrieval):
        split[i] = split_codes.setdefault(item["split"], len(split_codes))
        rec[i] = rec_codes.setdefault(item["record_id"], len(rec_codes))
        fam[i] = fam_codes.setdefault(item["family_id"], len(fam_codes))
        intext[i] = intext_codes.setdefault(item["input_text"], len(intext_codes))
        srcsha[i] = srcsha_codes.setdefault(
            item["evidence_anchor"]["source_text_sha256"], len(srcsha_codes)
        )
        stratum = strata_by_record.get(item["record_id"])
        if stratum:
            spec[i] = spec_codes.setdefault(stratum.get("primary_specialty"), len(spec_codes))
            qtype[i] = qtype_codes.setdefault(stratum.get("question_type"), len(qtype_codes))
            has_stratum[i] = True
        else:
            spec[i] = -1
            qtype[i] = -1

    # Neighborhood membership (primary_specialty OR question_type) is fixed per
    # (specialty, question) pair, so group queries and slice the sparse matrix
    # once per group instead of per query.
    matrix = matrix.astype(np.float32)  # 0/1 dot products are exact in float32
    query_columns_by_id: dict[str, np.ndarray] = {
        example_ids[i]: np.asarray(
            [token_columns[token] for token in query_token_sets[example_ids[i]] if token in token_columns],
            dtype=np.int64,
        )
        for i in range(n)
    }

    group_queries: dict[tuple[int, int], list[int]] = {}
    for i in range(n):
        if has_stratum[i]:
            group_queries.setdefault((int(spec[i]), int(qtype[i])), []).append(i)

    negatives_by_query: dict[str, list[tuple[dict[str, Any], int, list[str]]]] = {}
    qvec = np.zeros(matrix.shape[1], dtype=np.float32)
    previous_columns = np.empty(0, dtype=np.int64)

    for (g_spec, g_qtype), query_indices in group_queries.items():
        nbr = np.flatnonzero(has_stratum & ((spec == g_spec) | (qtype == g_qtype)))
        sub = matrix[nbr]
        for qi in query_indices:
            q_id = example_ids[qi]
            q_split = int(split[qi])
            q_rec = int(rec[qi])
            q_fam = int(fam[qi])
            q_intext = int(intext[qi])
            q_srcsha = int(srcsha[qi])
            mask = (
                (split[nbr] == q_split)
                & (rec[nbr] != q_rec)
                & (fam[nbr] != q_fam)
                & (intext[nbr] != q_intext)
                & (srcsha[nbr] != q_srcsha)
            )
            pass_pos = np.flatnonzero(mask)
            if pass_pos.size == 0:
                negatives_by_query[q_id] = []
                continue

            query_columns = query_columns_by_id[q_id]
            if previous_columns.size:
                qvec[previous_columns] = 0.0
            qvec[query_columns] = 1.0
            previous_columns = query_columns
            overlaps_all = sub @ qvec
            overlaps = overlaps_all[pass_pos]

            if pass_pos.size <= 3:
                chosen_global = nbr[pass_pos]
            else:
                threshold = int(np.partition(overlaps, -3)[-3])
                above_pos = pass_pos[overlaps > threshold]
                tied_pos = pass_pos[overlaps == threshold]
                above_global = nbr[above_pos]
                tied_global = nbr[tied_pos]
                need = 3 - above_pos.size
                order = sorted(
                    range(tied_global.size),
                    key=lambda k: _pair_tie(seed, q_id, example_ids[int(tied_global[k])]),
                )
                chosen_global = np.concatenate([above_global, tied_global[order[:need]]])

            negatives: list[tuple[dict[str, Any], int, list[str]]] = []
            for i in chosen_global:
                i = int(i)
                keys = []
                if spec[i] == g_spec:
                    keys.append("primary_specialty")
                if qtype[i] == g_qtype:
                    keys.append("question_type")
                negatives.append((retrieval[i], 0, keys))
            negatives_by_query[q_id] = negatives

    def select(query: dict[str, Any]) -> list[tuple[dict[str, Any], int, list[str]]]:
        return negatives_by_query[query["example_id"]]

    return select


def build_retrieval_pairs(
    examples: list[dict[str, Any]],
    strata_by_record: dict[str, dict[str, Any]],
    seed: int,
) -> list[dict[str, Any]]:
    """Build source positives and family-isolated medical-neighborhood negatives."""
    retrieval = [item for item in examples if item.get("task") == "evidence_retrieval"]
    pairs: list[dict[str, Any]] = []
    query_token_sets = {
        item["example_id"]: _tokens(item["instruction"] + " " + item["input_text"])
        for item in retrieval
    }
    document_token_sets = {
        item["example_id"]: _tokens(item["input_text"])
        for item in retrieval
    }
    built = _build_token_matrix(retrieval, document_token_sets)
    if built is None:
        select_negatives = _python_negative_selector(
            retrieval, strata_by_record, seed, query_token_sets, document_token_sets
        )
    else:
        matrix, token_columns, _positions = built
        select_negatives = _vectorized_negative_selector(
            retrieval, strata_by_record, seed, query_token_sets, matrix, token_columns
        )
    for query in sorted(retrieval, key=lambda item: item["example_id"]):
        query_stratum = strata_by_record.get(query["record_id"])
        if not query_stratum:
            raise TrainingCorpusError(f"missing biomedical stratum for record: {query['record_id']}")
        selected = [(query, 1, ["self_anchored_positive"])]
        selected.extend(select_negatives(query))
        for document, label, neighborhood_keys in selected:
            identity = f"{seed}:{query['example_id']}:{document['example_id']}:{label}"
            pair = {
                "schema_version": "1.0",
                "pair_id": "training-pair:" + hashlib.sha256(identity.encode()).hexdigest()[:20],
                "query_example_id": query["example_id"],
                "query_record_id": query["record_id"],
                "query_family_id": query["family_id"],
                "query_split": query["split"],
                "query_text": _retrieval_query(query),
                "document_example_id": document["example_id"],
                "document_record_id": document["record_id"],
                "document_family_id": document["family_id"],
                "document_split": document["split"],
                "document_text": document["input_text"],
                "label": label,
                "shared_medical_neighborhood": label == 0,
                "neighborhood_keys": neighborhood_keys,
                "label_status": (
                    "source_anchored_positive_weak_supervision"
                    if label == 1
                    else "candidate_hard_negative_not_gold"
                ),
                "evidence": [
                    f"query_anchor:{query['evidence_anchor']['source_text_sha256']}",
                    f"document_anchor:{document['evidence_anchor']['source_text_sha256']}",
                ],
            }
            pair["content_sha256"] = hashlib.sha256(
                canonical_json({key: value for key, value in pair.items() if key != "content_sha256"})
            ).hexdigest()
            validate_document(pair, "training_pair")
            pairs.append(pair)
    pairs.sort(key=lambda item: item["pair_id"])
    return pairs


def build_component_training_job(
    run_plan: dict[str, Any],
    component: str,
    model: dict[str, Any],
    optimization: dict[str, Any],
    resources: dict[str, Any],
    now: str,
    *,
    run_plan_path: str = "training-run-plan.json",
    run_plan_sha256: str | None = None,
    job_path: str | None = None,
    output_root: str = "training-output",
    runtime_lock_path: str = "metawingman/references/dependencies/python-training.lock.txt",
    runtime_lock_sha256: str,
    seed: int = 20260815,
) -> dict[str, Any]:
    validate_document(run_plan, "training_run_plan")
    if component not in run_plan["objectives"]:
        raise TrainingCorpusError(f"component objective is absent from run plan: {component}")
    dataset = run_plan["dataset"]
    reason_codes = []
    revision = str(model.get("revision") or "")
    tokenizer_revision = str(model.get("tokenizer_revision") or "")
    if not re.fullmatch(r"[a-f0-9]{40}", revision) or not re.fullmatch(r"[a-f0-9]{40}", tokenizer_revision):
        reason_codes.append("model_revision_not_immutable")
    if not model.get("declared_license"):
        reason_codes.append("model_license_unresolved")
    if dataset.get("development_examples", 0) < 1:
        reason_codes.append("development_data_missing")
    if component == "evidence_retrieval" and dataset.get("development_pairs", 0) < 1:
        reason_codes.append("development_pairs_missing")
    job = {
        "schema_version": "1.0",
        "job_id": f"metawingman-{component.replace('_', '-')}-v1",
        "created_at_utc": now,
        "component": component,
        "status": "blocked" if reason_codes else "ready_for_server_preflight",
        "reason_codes": sorted(set(reason_codes)),
        "model": {
            "repository_id": model["repository_id"],
            "revision": revision,
            "tokenizer_revision": tokenizer_revision,
            "model_card_url": model["model_card_url"],
            "declared_license": model.get("declared_license"),
            "release_intent": model.get("release_intent", "internal_research_only"),
        },
        "dataset": {
            "run_plan_path": run_plan_path,
            "run_plan_sha256": run_plan_sha256 or hashlib.sha256(canonical_json(run_plan)).hexdigest(),
            "examples_path": dataset["examples_path"],
            "examples_sha256": dataset["examples_sha256"],
            "pairs_path": dataset.get("pairs_path", "pairs.jsonl"),
            "pairs_sha256": dataset.get("pairs_sha256", "0" * 64),
            "train_examples": dataset["train_examples"],
            "development_examples": dataset["development_examples"],
            "train_pairs": dataset.get("train_pairs", 0),
            "development_pairs": dataset.get("development_pairs", 0),
            "family_isolation": True,
            "label_policy": "weak_candidates_not_gold",
            "release_status": "raw_text_redistribution_forbidden_weights_pending_license_review",
        },
        "optimization": dict(optimization),
        "resources": resources,
        "output": {
            "root": output_root,
            "checkpoint_every_steps": int(optimization.get("checkpoint_every_steps", 250)),
            "maximum_checkpoints": int(optimization.get("maximum_checkpoints", 3)),
            "resume_checkpoint_hashes": list(optimization.get("resume_checkpoint_hashes", [])),
        },
        "runtime": {
            "lock_path": runtime_lock_path,
            "lock_sha256": runtime_lock_sha256,
            "python": "3.12",
            "cuda_required": resources.get("gpu_count", 0) > 0,
        },
        "seed": seed,
        "command_argv": [
            "python",
            "metawingman/scripts/run_component_training.py",
            job_path or f"validation-output/training-corpus/jobs/{component}.json",
            "--root",
            ".",
        ],
    }
    for transient in ("checkpoint_every_steps", "maximum_checkpoints", "resume_checkpoint_hashes"):
        job["optimization"].pop(transient, None)
    validate_document(job, "component_training_job")
    return job


def _resolve_job_path(root: Path, value: str) -> Path:
    root = root.resolve()
    path = (root / value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise TrainingCorpusError(f"component training path escapes root: {value}") from exc
    return path


def _locked_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "==" in line:
            name, version = line.split("==", 1)
            versions[name.casefold()] = version
    return versions


def preflight_component_training(
    job: dict[str, Any], root: Path, *, inspect_server: bool = False
) -> dict[str, Any]:
    reason_codes: list[str] = []
    try:
        validate_document(job, "component_training_job")
    except Exception:
        return {"manifest_valid": False, "ready": False, "training_started": False, "reason_codes": ["job_schema_invalid"]}
    if not re.fullmatch(r"[a-f0-9]{40}", job["model"]["revision"]) or not re.fullmatch(
        r"[a-f0-9]{40}", job["model"]["tokenizer_revision"]
    ):
        reason_codes.append("model_revision_not_immutable")
    if not job["model"]["declared_license"]:
        reason_codes.append("model_license_unresolved")
    for key in ("run_plan", "examples", "pairs"):
        path = _resolve_job_path(root, job["dataset"][f"{key}_path"])
        if not path.is_file():
            reason_codes.append(f"{key}_file_missing")
        elif sha256_file(path) != job["dataset"][f"{key}_sha256"]:
            reason_codes.append(f"{key}_hash_mismatch")
    lock_path = _resolve_job_path(root, job["runtime"]["lock_path"])
    if not lock_path.is_file():
        reason_codes.append("runtime_lock_missing")
    elif sha256_file(lock_path) != job["runtime"]["lock_sha256"]:
        reason_codes.append("runtime_lock_hash_mismatch")
    _resolve_job_path(root, job["output"]["root"])
    if job["dataset"]["development_examples"] < 1:
        reason_codes.append("development_data_missing")
    if job["component"] == "evidence_retrieval" and job["dataset"]["development_pairs"] < 1:
        reason_codes.append("development_pairs_missing")
    if job["status"] != "ready_for_server_preflight":
        reason_codes.extend(job["reason_codes"] or ["job_not_ready_for_server_preflight"])
    if inspect_server:
        if shutil.disk_usage(root).free < job["resources"]["storage_gib"] * 1024**3:
            reason_codes.append("insufficient_free_storage")
        locks = _locked_versions(lock_path) if lock_path.is_file() else {}
        for package, expected in locks.items():
            try:
                actual = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                reason_codes.append(f"package_missing_{package.replace('-', '_')}")
            else:
                if actual != expected:
                    reason_codes.append(f"package_version_mismatch_{package.replace('-', '_')}")
        if job["resources"]["gpu_count"]:
            try:
                completed = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                completed = None
            if completed is None or completed.returncode != 0:
                reason_codes.append("cuda_runtime_unverified")
            else:
                memories = [int(value.strip()) / 1024 for value in completed.stdout.splitlines() if value.strip().isdigit()]
                if len(memories) < job["resources"]["gpu_count"]:
                    reason_codes.append("insufficient_gpu_count")
                elif any(value < job["resources"]["gpu_memory_gib_each"] for value in memories[: job["resources"]["gpu_count"]]):
                    reason_codes.append("insufficient_gpu_memory")
    else:
        reason_codes.extend(["server_hardware_unverified", "cuda_runtime_unverified", "python_packages_unverified"])
    pending = {"server_hardware_unverified", "cuda_runtime_unverified", "python_packages_unverified"}
    scientific_blockers = sorted(code for code in set(reason_codes) if code not in pending)
    return {
        "manifest_valid": True,
        "ready": not reason_codes,
        "training_started": False,
        "reason_codes": sorted(set(reason_codes)),
        "scientific_blockers": scientific_blockers,
        "server_checks_pending": sorted(pending & set(reason_codes)),
    }


def audit_training_dataset(
    plan: dict[str, Any], manifest: dict[str, Any], examples: list[dict[str, Any]],
    run_plan: dict[str, Any], artifact_root: Path, manifest_path: Path, examples_path: Path,
) -> dict[str, Any]:
    """Verify that a frozen training dataset can be replayed without split or file drift."""
    issues: list[str] = []
    for document, schema in (
        (plan, "training_corpus_plan"),
        (manifest, "training_document_manifest"),
        (run_plan, "training_run_plan"),
    ):
        try:
            validate_document(document, schema)
        except Exception as exc:
            issues.append(str(exc))
    for index, example in enumerate(examples, start=1):
        try:
            validate_document(example, "training_example")
        except Exception as exc:
            issues.append(f"example {index}: {exc}")

    plan_records = {item["record_id"]: item for item in plan.get("records", [])}
    manifest_documents = {item["document_id"]: item for item in manifest.get("documents", [])}
    expected_plan_hash = hashlib.sha256(canonical_json(plan)).hexdigest()
    if manifest.get("plan_id") != plan.get("plan_id") or manifest.get("plan_sha256") != expected_plan_hash:
        issues.append("manifest is not bound to the supplied canonical training plan")
    if len(manifest_documents) != len(manifest.get("documents", [])):
        issues.append("manifest contains duplicate document_id values")
    example_ids = [item.get("example_id") for item in examples]
    if len(set(example_ids)) != len(example_ids):
        issues.append("examples contain duplicate example_id values")

    family_splits: dict[str, set[str]] = defaultdict(set)
    artifact_hashes: dict[str, str] = {}
    root = artifact_root.resolve()
    for document in manifest.get("documents", []):
        family_splits[document["family_id"]].add(document["split"])
        planned = plan_records.get(document["record_id"])
        if planned is None:
            issues.append(f"manifest record is absent from plan: {document['record_id']}")
        elif planned["family_id"] != document["family_id"] or planned["split"] != document["split"]:
            issues.append(f"manifest family/split drift: {document['record_id']}")
        for artifact in document["artifacts"]:
            try:
                path = _safe_destination(root, artifact["relative_path"])
            except TrainingCorpusError as exc:
                issues.append(str(exc))
                continue
            if not path.is_file():
                issues.append(f"artifact is missing: {artifact['relative_path']}")
                continue
            actual_hash = sha256_file(path)
            if path.stat().st_size != artifact["bytes"] or actual_hash != artifact["sha256"]:
                issues.append(f"artifact hash or size drift: {artifact['relative_path']}")
            artifact_hashes[artifact["sha256"]] = artifact["relative_path"]
    for family, splits in sorted(family_splits.items()):
        if len(splits) > 1:
            issues.append(f"review family crosses splits: {family}")

    split_counts = Counter()
    for example in examples:
        split_counts[example["split"]] += 1
        source = manifest_documents.get(example["document_id"])
        if source is None:
            issues.append(f"example references unknown document: {example['example_id']}")
        elif source["family_id"] != example["family_id"] or source["split"] != example["split"]:
            issues.append(f"example family/split drift: {example['example_id']}")
        if example["evidence_anchor"]["artifact_sha256"] not in artifact_hashes:
            issues.append(f"example evidence artifact is unknown: {example['example_id']}")
        passage = example["input_text"].split("\n\n", 1)
        if len(passage) != 2 or hashlib.sha256(passage[1].encode("utf-8")).hexdigest() != example["evidence_anchor"]["source_text_sha256"]:
            issues.append(f"example source-text anchor drift: {example['example_id']}")
        unhashed = {key: value for key, value in example.items() if key != "content_sha256"}
        actual_content_hash = hashlib.sha256(canonical_json(unhashed)).hexdigest()
        if actual_content_hash != example["content_sha256"]:
            issues.append(f"example content hash drift: {example['example_id']}")
        if example.get("gold_label") is not False:
            issues.append(f"weak-supervision dataset contains a gold label: {example['example_id']}")

    expected_dataset = run_plan.get("dataset", {})
    if manifest_path.is_file() and sha256_file(manifest_path) != expected_dataset.get("manifest_sha256"):
        issues.append("run plan manifest hash does not match the frozen manifest")
    if examples_path.is_file() and sha256_file(examples_path) != expected_dataset.get("examples_sha256"):
        issues.append("run plan examples hash does not match the frozen JSONL")
    if split_counts["train"] != expected_dataset.get("train_examples"):
        issues.append("run plan train example count does not match JSONL")
    if split_counts["development"] != expected_dataset.get("development_examples"):
        issues.append("run plan development example count does not match JSONL")
    if expected_dataset.get("held_out_examples") != 0:
        issues.append("held-out examples are forbidden in the provisional training dataset")
    return {
        "valid": not issues,
        "issues": issues,
        "summary": {
            "planned_records": len(plan_records), "manifest_documents": len(manifest_documents),
            "artifacts": len(artifact_hashes), "examples": len(examples),
            "train_examples": split_counts["train"],
            "development_examples": split_counts["development"], "held_out_examples": 0,
            "families": len(family_splits),
        },
    }


def build_training_run_plan(
    manifest: dict[str, Any], manifest_path: Path, examples_path: Path, examples: list[dict[str, Any]],
    *, run_plan_id: str, created_at_utc: str | None = None,
    pairs_path: Path | None = None,
    pairs: list[dict[str, Any]] | None = None,
    biomedical_strata_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    validate_document(manifest, "training_document_manifest")
    counts = Counter(item["split"] for item in examples)
    objectives = sorted({item["task"] for item in examples})
    if not objectives:
        raise TrainingCorpusError("cannot freeze a training run plan without examples")
    pairs = pairs or []
    pair_counts = Counter(item["query_split"] for item in pairs)
    ready = pairs_path is not None and bool(pairs) and counts["development"] > 0 and pair_counts["development"] > 0
    plan = {
        "schema_version": "1.1" if ready else "1.0", "run_plan_id": run_plan_id,
        "created_at_utc": created_at_utc or utc_now(),
        "dataset": {
            "manifest_path": manifest_path.as_posix(), "manifest_sha256": sha256_file(manifest_path),
            "examples_path": examples_path.as_posix(), "examples_sha256": sha256_file(examples_path),
            "train_examples": counts["train"], "development_examples": counts["development"],
            "held_out_examples": 0,
        },
        "model_contract": {
            "provider_neutral": True, "base_model": None, "revision": None,
            "tokenizer_revision": None, "license_review_required_before_training": True,
        },
        "objectives": objectives,
        "evaluation": {
            "unit": "review_family",
            "metrics": ["macro_f1", "family_bootstrap_accuracy", "retrieval_recall_at_k", "selective_accuracy", "abstention_rate"],
            "selection_uses_development_only": True, "scientific_claims_disabled": True,
        },
        "contamination_controls": {
            "family_isolation": True, "journal_feature_forbidden": True,
            "published_answer_is_not_oracle": True, "model_memory_risk_recorded": True,
        },
        "execution_state": "planned_not_trained",
    }
    if ready and pairs_path is not None:
        plan["dataset"].update({
            "pairs_path": pairs_path.as_posix(),
            "pairs_sha256": sha256_file(pairs_path),
            "train_pairs": pair_counts["train"],
            "development_pairs": pair_counts["development"],
            "biomedical_strata_counts": dict(sorted((biomedical_strata_counts or {}).items())),
        })
        plan["objective_readiness"] = {
            "section_role_classification": "ready_for_server_preflight",
            "evidence_retrieval": "ready_for_server_preflight",
        }
        plan["execution_state"] = "ready_for_server_preflight"
    validate_document(plan, "training_run_plan")
    return plan
