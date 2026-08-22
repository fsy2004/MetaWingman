from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from metawingman.scripts.build_protocol_distillation_bootstrap import build_bootstrap
from metawingman.scripts.metawingman_core.distillation_readiness import audit_distillation_readiness


ROOT = Path(__file__).resolve().parents[1]


class ProtocolDistillationBootstrapTests(unittest.TestCase):
    def test_methods_only_bootstrap_is_trainable_and_excludes_results(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root = Path(tmp)
            sections = [
                "Eligibility criteria", "Information sources", "Study selection and data collection",
                "Data items", "Risk of bias in individual studies", "Summary measures and synthesis",
                "Additional analyses", "Credibility assessment", "Patient and public involvement",
            ]
            xml = "<article><body><sec sec-type='methods'><title>Methods</title>" + "".join(
                f"<sec><title>{title}</title><p>{title} was specified prospectively with enough source-bound methodological detail to create one verified training action without using any published result.</p></sec>"
                for title in sections
            ) + "</sec><sec sec-type='results'><title>Results</title><p>FORBIDDEN_RESULT_SENTINEL</p></sec></body></article>"
            article = root / "article.nxml"
            article.write_text(xml, encoding="utf-8")
            registry = json.loads((ROOT / "research/direct-evidence-case-registry-v1.json").read_text(encoding="utf-8"))
            registry_path = root / "registry.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            result = build_bootstrap(
                article_xml=article, case_registry_path=registry_path,
                teacher_path=ROOT / "metawingman/references/protocol-distillation-teacher-v1.json",
                prompt_path=ROOT / "metawingman/references/protocol-distillation-prompt-v1.json",
                output_dir=root / "out", created_at_utc="2026-08-22T09:30:00Z",
            )
            self.assertEqual(result["examples"], 9)
            export_path = Path(result["paths"]["export"])
            self.assertNotIn("FORBIDDEN_RESULT_SENTINEL", export_path.read_text(encoding="utf-8"))
            readiness = audit_distillation_readiness(
                export_paths=[export_path], case_registry_path=registry_path,
                lineage_manifest_path=Path(result["paths"]["lineage"]),
                revocation_manifest_path=Path(result["paths"]["revocations"]),
                artifact_root=ROOT,
            )
            self.assertTrue(readiness["ready_for_student_training"], readiness["blockers"])


if __name__ == "__main__":
    unittest.main()
