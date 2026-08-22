from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.update_readme import (
    compute_metrics,
    local_link_errors,
    render_inventory,
    update_generated_blocks,
)


class ReadmeUpdateTests(unittest.TestCase):
    def test_compute_metrics_reads_canonical_source_not_generated_copies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in (
                "toolkit/R/01_effect.R",
                "toolkit/R/02_model.R",
                "metawingman/scripts/r/manifests/a.json",
                "metawingman/scripts/r/adapters/run_pairwise.R",
                "metawingman/scripts/a.py",
                "metawingman/schemas/a.json",
                ".agents/skills/metawingman/scripts/generated.py",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            self.assertEqual(
                compute_metrics(root),
                {"r_modules": 2, "manifests": 1, "adapters": 1, "python_entrypoints": 1, "schemas": 1},
            )

    def test_update_generated_blocks_refreshes_metrics_and_inventory_together(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in (
                "toolkit/R/01_effect.R",
                "metawingman/scripts/r/manifests/pairwise.json",
                "metawingman/scripts/r/adapters/run_pairwise.R",
                "metawingman/scripts/run_review.py",
                "metawingman/schemas/review.json",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            source = (
                "intro\n"
                "<!-- readme-metrics:start -->\nstale badge\n<!-- readme-metrics:end -->\n"
                "manual\n"
                "<!-- readme-inventory:start -->\nstale table\n<!-- readme-inventory:end -->\n"
                "tail\n"
            )
            updated = update_generated_blocks(root, source, version="v9.9.9")
        self.assertNotIn("release-v9.9.9", updated)
        self.assertNotIn("img.shields", updated)
        self.assertIn("| JSON schemas | 1 |", updated)
        self.assertIn("| R adapters | 1 |", updated)
        self.assertIn("manual", updated)
        self.assertTrue(updated.endswith("tail\n"))

    def test_render_inventory_uses_only_canonical_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in (
                "toolkit/R/01_effect.R",
                "toolkit/R/02_model.R",
                "metawingman/scripts/r/manifests/a.json",
                "metawingman/scripts/r/adapters/run_pairwise.R",
                "metawingman/scripts/run_review.py",
                "metawingman/schemas/review.json",
                ".agents/skills/metawingman/scripts/generated.py",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x", encoding="utf-8")
            inventory = render_inventory(root)
        self.assertEqual(
            inventory,
            "| Repository metric | Current |\n"
            "|---|---:|\n"
            "| Python entry points | 1 |\n"
            "| JSON schemas | 1 |\n"
            "| R analysis modules | 2 |\n"
            "| R adapter manifests | 1 |\n"
            "| R adapters | 1 |",
        )

    def test_replace_block_preserves_surrounding_manual_content(self):
        from scripts.update_readme import replace_block

        source = "intro\n<!-- readme-metrics:start -->\nstale\n<!-- readme-metrics:end -->\nmanual\n"
        self.assertEqual(
            replace_block(source, "readme-metrics", "fresh"),
            "intro\n<!-- readme-metrics:start -->\nfresh\n<!-- readme-metrics:end -->\nmanual\n",
        )

    def test_local_link_errors_reports_missing_repo_paths_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            (root / "docs" / "ok.md").write_text("ok", encoding="utf-8")
            text = "[ok](docs/ok.md) [missing](docs/missing.md) [web](https://example.org)"
            self.assertEqual(local_link_errors(root, text), ["docs/missing.md"])


if __name__ == "__main__":
    unittest.main()
