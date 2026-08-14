from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.build_skill_bundle import BundleBuildError, _assert_source_tree_safe, _stage
from scripts.verify_skill_bundle import BundleVerificationError, _reject_links, verify_bundle
from scripts.package_skill_release import package_skill
from scripts.generate_release_metadata import generate_metadata


ROOT = Path(__file__).resolve().parents[1]


class SkillDistributionTests(unittest.TestCase):
    def test_staged_bundle_verifies_and_has_no_volatile_git_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "metawingman"
            manifest = _stage(ROOT, bundle)
            result = verify_bundle(bundle)
            self.assertTrue(result["valid"])
            self.assertEqual(result["source_tree_sha256"], manifest["source_tree_sha256"])
            self.assertNotIn("git_commit", manifest)
            self.assertNotIn("git_dirty", manifest)

    def test_tampered_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "metawingman"
            _stage(ROOT, bundle)
            skill = bundle / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\ntampered\n", encoding="utf-8")
            with self.assertRaises(BundleVerificationError):
                verify_bundle(bundle)

    def test_marketplace_points_to_valid_plugin(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
        )
        entry = next(item for item in marketplace["plugins"] if item["name"] == "metawingman")
        plugin = (ROOT / entry["source"]["path"]).resolve()
        plugin.relative_to(ROOT)
        manifest = json.loads((plugin / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "metawingman")
        self.assertEqual(manifest["interface"]["category"], "Research")

    def test_bundle_is_host_model_skill_without_direct_model_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "metawingman"
            manifest = _stage(ROOT, bundle)
            self.assertEqual(manifest["requirements"]["execution_model"], "host_model_only")
            self.assertEqual(manifest["requirements"]["direct_model_api"], "not bundled")
            forbidden = [
                "references/deepseek-model-registry.template.json",
                "scripts/configure_provider_secret.py",
                "scripts/probe_deepseek.py",
                "scripts/propose_topics.py",
                "scripts/metawingman_core/deepseek_provider.py",
                "scripts/metawingman_core/model_provider.py",
                "scripts/metawingman_core/provider_secrets.py",
                "scripts/metawingman_core/topic_proposer.py",
            ]
            for relative in forbidden:
                self.assertFalse((bundle / relative).exists(), relative)
            skill_text = (bundle / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("uses the host agent's model and tools", skill_text)
            self.assertNotIn("DEEPSEEK_API_KEY", skill_text)

    def test_release_archive_is_deterministic_and_rooted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            _stage(ROOT, bundle)
            first = package_skill(bundle, root / "first")
            second = package_skill(bundle, root / "second")
            self.assertEqual(first["sha256"], second["sha256"])
            with zipfile.ZipFile(first["archive"]) as handle:
                names = handle.namelist()
            self.assertTrue(names)
            self.assertTrue(all(name.startswith("metawingman/") for name in names))
            self.assertIn("metawingman/SKILL.md", names)

    def test_release_metadata_binds_archive_and_declares_unsigned_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "bundle"
            _stage(ROOT, bundle)
            packaged = package_skill(bundle, root / "dist")
            result = generate_metadata(bundle, Path(packaged["archive"]), root / "metadata")
            self.assertFalse(result["publisher_authenticated"])
            sbom = json.loads(Path(result["sbom"]).read_text(encoding="utf-8"))
            self.assertEqual(sbom["spdxVersion"], "SPDX-2.3")
            self.assertEqual(sbom["packages"][0]["checksums"][0]["checksumValue"], packaged["sha256"])
            provenance = json.loads(Path(result["unsigned_provenance"]).read_text(encoding="utf-8"))
            self.assertEqual(provenance["subject"][0]["digest"]["sha256"], packaged["sha256"])
            self.assertTrue(any(item["name"] == "jsonschema" for item in sbom["packages"]))

    def test_source_tree_links_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ordinary = root / "outside.txt"
            ordinary.write_text("outside", encoding="utf-8")
            with patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda path: path == ordinary):
                with self.assertRaises(BundleBuildError):
                    _assert_source_tree_safe(root)

    def test_bundle_verifier_rejects_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ordinary = root / "linked.txt"
            ordinary.write_text("fixture", encoding="utf-8")
            with patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda path: path == ordinary):
                with self.assertRaises(BundleVerificationError):
                    _reject_links(root)


if __name__ == "__main__":
    unittest.main()
