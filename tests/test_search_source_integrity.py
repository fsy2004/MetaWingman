from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

import search_sources  # noqa: E402


class SearchIntegrityTests(unittest.TestCase):
    def test_pubmed_publication_date_prefers_exact_article_date(self) -> None:
        article = ET.fromstring("""
        <PubmedArticle><MedlineCitation><Article>
          <ArticleDate DateType="Electronic"><Year>2020</Year><Month>06</Month><Day>03</Day></ArticleDate>
          <Journal><JournalIssue><PubDate><Year>2020</Year><Month>Jun</Month><Day>09</Day></PubDate></JournalIssue></Journal>
        </Article></MedlineCitation></PubmedArticle>
        """)
        self.assertEqual(search_sources.publication_date_from_article(article), "2020-06-03")

    def test_pubmed_construct_annotations_are_exported_from_source_xml(self) -> None:
        article = ET.fromstring("""
        <PubmedArticle><MedlineCitation><Article>
          <ArticleTitle>Health technology assessment of treatment</ArticleTitle>
          <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
          <DataBankList><DataBank><AccessionNumberList><AccessionNumber>ISRCTN12345678</AccessionNumber></AccessionNumberList></DataBank></DataBankList>
        </Article><MeshHeadingList><MeshHeading><DescriptorName>Treatment Outcome</DescriptorName></MeshHeading></MeshHeadingList>
        </MedlineCitation></PubmedArticle>
        """)
        value = search_sources.pubmed_construct_annotations(article)
        self.assertEqual(value["registry_ids"], ["ISRCTN12345678"])
        self.assertEqual(value["study_family_ids"], ["ISRCTN12345678"])
        self.assertEqual(value["decision_anchor_type"], "health_technology_assessment")
        self.assertEqual(value["mesh_terms"], ["Treatment Outcome"])

    def test_count_mismatch_and_duplicates_fail(self) -> None:
        with self.assertRaises(search_sources.SearchIntegrityError):
            search_sources.assert_complete([{"record_id": "one"}], 2, 0, "fixture")
        with self.assertRaises(search_sources.SearchIntegrityError):
            search_sources.assert_complete(
                [{"record_id": "one"}, {"record_id": "one"}], 2, 0, "fixture"
            )
        search_sources.assert_complete([{"record_id": "one"}], 10, 1, "fixture")

    def test_clinical_trials_repeated_page_token_fails(self) -> None:
        page = {
            "totalCount": 2,
            "studies": [{
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT00000001", "briefTitle": "Fixture"},
                    "descriptionModule": {"briefSummary": "Fixture"},
                }
            }],
            "nextPageToken": "same-token",
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "search_sources.fetch", return_value=json.dumps(page).encode("utf-8")
        ):
            with self.assertRaises(search_sources.SearchIntegrityError):
                search_sources.clinical_trials("fixture", 0, Path(directory))

    def test_fetch_rejects_oversized_response(self) -> None:
        response = io.BytesIO(b"12345")
        response.geturl = lambda: "https://example.org/api"
        response.headers = {"Content-Length": "5"}
        opener = Mock()
        opener.open.return_value = response
        with (
            tempfile.TemporaryDirectory() as directory,
            patch("search_sources.validate_public_https_url", side_effect=lambda value: value),
            patch("search_sources.public_https_opener", return_value=opener),
        ):
            with self.assertRaises(search_sources.SearchIntegrityError):
                search_sources.fetch(
                    "https://example.org/api", Path(directory), "fixture",
                    retries=1, max_bytes=4,
                )


if __name__ == "__main__":
    unittest.main()
