"""Reproducible, source-anchored training-corpus primitives."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

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


def _request_bytes(url: str, *, max_bytes: int, attempts: int = 3) -> tuple[bytes, str]:
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
                while True:
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


def _json_api(url: str, max_bytes: int = 5 * 1024 * 1024) -> dict[str, Any]:
    body, _ = _request_bytes(url, max_bytes=max_bytes)
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingCorpusError(f"invalid JSON response from training source: {exc}") from exc
    if not isinstance(value, dict):
        raise TrainingCorpusError("training source JSON response is not an object")
    return value


def _oa_license(pmcid: str) -> tuple[str | None, str]:
    url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=" + urllib.parse.quote(pmcid)
    body, _ = _request_bytes(url, max_bytes=2 * 1024 * 1024)
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


def _full_text_urls(record: dict[str, Any]) -> tuple[str | None, str]:
    query = f"EXT_ID:{record['pmid']} AND SRC:MED" if record.get("pmid") else f"PMC_ID:{record['pmcid']}"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({
        "query": query, "format": "json", "resultType": "core", "pageSize": 1,
    })
    payload = _json_api(url)
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
            api_license, integrity_status = _oa_license(record["pmcid"])
            if api_license:
                retrieved_license = _normalise_license(api_license)
            if integrity_status == "rejected_retracted":
                raise TrainingCorpusError("PMC OA service marks the article as retracted")
            if retrieved_license not in allowed:
                raise TrainingCorpusError(f"article license is outside the frozen allowlist: {retrieved_license}")
            pdf_url, xml_url = _full_text_urls(record)
        except TrainingCorpusError as exc:
            failures.append(str(exc))

        if not failures and pdf_url:
            try:
                body, final_url = _request_bytes(pdf_url, max_bytes=max_file_bytes)
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
        elif not failures:
            failures.append("no_open_access_pdf_url")

        if xml_url is not None and integrity_status == "verified_not_retracted" and retrieved_license in allowed:
            try:
                body, final_url = _request_bytes(xml_url, max_bytes=max_file_bytes)
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
                    "instruction": instruction, "input_text": f"Section title: {title}\n\n{text}",
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
) -> dict[str, Any]:
    validate_document(manifest, "training_document_manifest")
    counts = Counter(item["split"] for item in examples)
    objectives = sorted({item["task"] for item in examples})
    if not objectives:
        raise TrainingCorpusError("cannot freeze a training run plan without examples")
    plan = {
        "schema_version": "1.0", "run_plan_id": run_plan_id,
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
    validate_document(plan, "training_run_plan")
    return plan
