from __future__ import annotations

import socket
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "metawingman/scripts"
sys.path.insert(0, str(SCRIPTS))

from metawingman_core.network_security import (  # noqa: E402
    PublicNetworkError,
    PublicHTTPSRedirectHandler,
    validate_public_https_url,
)


def address_info(address: str) -> list[tuple[object, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


class NetworkBoundaryTests(unittest.TestCase):
    def test_public_https_is_accepted(self) -> None:
        with patch("socket.getaddrinfo", return_value=address_info("93.184.216.34")):
            self.assertEqual(
                validate_public_https_url("https://example.org/paper.pdf"),
                "https://example.org/paper.pdf",
            )

    def test_private_loopback_credentials_and_nonstandard_ports_are_rejected(self) -> None:
        with patch("socket.getaddrinfo", return_value=address_info("127.0.0.1")):
            with self.assertRaises(PublicNetworkError):
                validate_public_https_url("https://example.org/private")
        for url in (
            "http://example.org/file",
            "https://user:pass@example.org/file",
            "https://example.org:8443/file",
            "https://127.0.0.1/file",
        ):
            with self.subTest(url=url), self.assertRaises(PublicNetworkError):
                validate_public_https_url(url)

    def test_redirect_to_private_address_is_rejected(self) -> None:
        handler = PublicHTTPSRedirectHandler()
        with self.assertRaises(PublicNetworkError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1/secret")


class ProjectPathBoundaryTests(unittest.TestCase):
    def test_init_review_rejects_slug_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "reviews"
            root.mkdir()
            escaped = root.parent / "escaped"
            process = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_review.py"),
                    "--name", "Adversarial path test",
                    "--root", str(root),
                    "--slug", "../escaped",
                    "--profile", "intervention",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(escaped.exists())

    def test_project_validator_rejects_freeze_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_review.py"),
                    "--name", "Freeze path test",
                    "--root", str(root),
                    "--slug", "review",
                    "--profile", "intervention",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            project = root / "review"
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            freeze = project / "06_analysis/freeze_manifest.json"
            freeze.write_text(json.dumps({
                "status": "frozen",
                "created_at": "2026-08-13T00:00:00Z",
                "files": [{"path": "../outside.txt", "sha256": "0" * 64}],
            }), encoding="utf-8")
            validation = subprocess.run(
                [sys.executable, str(SCRIPTS / "validate_project.py"), str(project)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertNotEqual(validation.returncode, 0)
            self.assertIn("escapes project root", validation.stdout)


if __name__ == "__main__":
    unittest.main()
