"""Extract explicit construct annotations from one PubMed XML article."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


_REGISTRY_PATTERNS = (
    re.compile(r"\bNCT\d{8}\b", re.IGNORECASE),
    re.compile(r"\bISRCTN\d{8}\b", re.IGNORECASE),
    re.compile(r"\bACTRN\d{14}\b", re.IGNORECASE),
    re.compile(r"\bChiCTR[-A-Za-z0-9]+\b", re.IGNORECASE),
)


def _strings(nodes: list[ET.Element]) -> list[str]:
    return list(dict.fromkeys(
        value for node in nodes
        if (value := "".join(node.itertext()).strip())
    ))


def pubmed_construct_annotations(article: ET.Element) -> dict[str, Any]:
    """Keep source-provided terms and identities without inventing domains or families."""
    mesh_terms = _strings(article.findall(".//MeshHeadingList/MeshHeading/DescriptorName"))
    publication_types = _strings(article.findall(".//Article/PublicationTypeList/PublicationType"))
    source_text = " ".join(article.itertext())
    registry_ids = sorted({
        match.group(0).upper() if not match.group(0).casefold().startswith("chictr") else match.group(0)
        for pattern in _REGISTRY_PATTERNS for match in pattern.finditer(source_text)
    })
    normalized_types = {value.casefold() for value in publication_types}
    title = " ".join(_strings(article.findall(".//Article/ArticleTitle"))).casefold()
    anchor: str | None = None
    if normalized_types & {"guideline", "practice guideline"}:
        anchor = "guideline"
    elif "health technology assessment" in title:
        anchor = "health_technology_assessment"
    elif any(phrase in title for phrase in ("research priority", "priority setting", "research agenda")):
        anchor = "priority_statement"
    elif "stakeholder" in title and any(term in title for term in ("decision", "consensus", "priority")):
        anchor = "stakeholder_decision"
    result: dict[str, Any] = {
        "mesh_terms": mesh_terms,
        "publication_types": publication_types,
        "registry_ids": registry_ids,
        "study_family_ids": registry_ids,
        "construct_annotation_basis": "explicit_pubmed_xml_v1",
    }
    if anchor is not None:
        result["decision_anchor_type"] = anchor
    return result
