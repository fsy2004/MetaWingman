from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

import search_sources  # noqa: E402


class SearchIntegrityTests(unittest.TestCase):
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
