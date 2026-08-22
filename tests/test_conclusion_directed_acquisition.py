import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from metawingman.scripts.metawingman_core.conclusion_directed_acquisition import (
    AcquisitionError,
    CONFIGURATIONS,
    lock_acquisition_outputs,
    interpret_candidate_response,
    parse_candidate_response,
    parse_query_response,
    interpret_query_response,
    rank_candidate_ids,
    balanced_round_robin,
    reciprocal_rank_fusion,
    replay_verifier_counterfactual,
    validate_acquisition_plan,
    validate_embedding_cache,
    verify_candidates,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConclusionDirectedAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.operational = self.root / "operational"
        self.sealed = self.root / "sealed"
        self.operational.mkdir()
        self.sealed.mkdir()
        self.corpus = self.operational / "corpus.jsonl"
        rows = [
            {"id": "a", "title": "Antimicrobial resistance", "abstract": "resistance burden", "cutoff_verification": {"status": "passed", "conservative_latest_date": "2020-01-01", "cutoff": "2021-08-31"}},
            {"id": "b", "title": "Diagnostic accuracy", "abstract": "sensitivity specificity", "cutoff_verification": {"status": "passed", "conservative_latest_date": "2021-07-01", "cutoff": "2021-08-31"}},
            {"id": "late", "title": "Later evidence", "abstract": "future", "cutoff_verification": {"status": "passed", "conservative_latest_date": "2022-01-01", "cutoff": "2021-08-31"}},
        ]
        self.corpus.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        self.reference = self.sealed / "published-reference.xlsx"
        self.reference.write_bytes(b"sealed-reference")
        self.prompt = self.operational / "prompt.txt"
        self.prompt.write_text("Generate conclusion claims and retrieval queries.", encoding="utf-8")
        self.provider = self.operational / "provider.json"
        self.provider.write_text(json.dumps({"model": "deepseek-v4-flash"}), encoding="utf-8")
        self.checkpoints = []
        seeds = [20260820, 20260821, 20260822]
        for seed in seeds:
            query = self.operational / f"query-{seed}"
            document = self.operational / f"document-{seed}"
            query.mkdir(); document.mkdir()
            (query / "model.safetensors").write_bytes(f"query-{seed}".encode())
            (document / "model.safetensors").write_bytes(f"document-{seed}".encode())
            self.checkpoints.append({
                "seed": seed,
                "query_path": str(query), "query_sha256": _sha(query / "model.safetensors"),
                "document_path": str(document), "document_sha256": _sha(document / "model.safetensors"),
            })
        self.plan = {
            "schema_version": "1.0",
            "plan_id": "ag-rdt-acquisition-r1",
            "frozen_at_utc": "2026-08-21T00:00:00Z",
            "case": {
                "case_id": "ag-rdt-living-update",
                "review_family_id": "ag-rdt",
                "historical_cutoff": "2021-08-31",
                "operational_corpus_path": str(self.corpus),
                "operational_corpus_sha256": _sha(self.corpus),
                "sealed_reference_path": str(self.reference),
                "sealed_reference_sha256": _sha(self.reference),
                "operational_question": "What is the diagnostic accuracy of commercial SARS-CoV-2 antigen rapid tests?",
                "eligibility_criteria": ["commercial antigen test", "RT-PCR reference standard"],
                "generic_queries": ["SARS-CoV-2 antigen rapid diagnostic test accuracy"],
            },
            "runtime": {
                "model_id": "deepseek-v4-flash",
                "provider_config_path": str(self.provider),
                "provider_config_sha256": _sha(self.provider),
                "prompt_path": str(self.prompt),
                "prompt_sha256": _sha(self.prompt),
                "matched_budget": {"max_model_calls": 1, "max_input_tokens": 12000, "max_output_tokens": 2048, "retry_limit": 0, "wall_seconds": 600},
            },
            "checkpoints": self.checkpoints,
            "configurations": list(CONFIGURATIONS),
            "seeds": seeds,
            "slots": [
                {"configuration_id": config, "seed": seed}
                for config in CONFIGURATIONS for seed in seeds
            ],
        }

    def tearDown(self):
        self.tempdir.cleanup()

    def test_exact_factorial_and_three_checkpoint_seeds_validate(self):
        validated = validate_acquisition_plan(deepcopy(self.plan))
        self.assertEqual(len(validated["slots"]), 12)
        self.assertEqual(
            validated["capabilities"]["full-conclusion-directed-verified"],
            {"conclusion_directed": True, "source_verifier": True},
        )

    def test_unknown_or_missing_slot_and_checkpoint_hash_drift_fail_closed(self):
        for mutation in ("unknown", "missing", "hash"):
            plan = deepcopy(self.plan)
            if mutation == "unknown":
                plan["configurations"][0] = "posthoc-arm"
            elif mutation == "missing":
                plan["slots"].pop()
            else:
                plan["checkpoints"][0]["query_sha256"] = "0" * 64
            with self.subTest(mutation=mutation), self.assertRaises(AcquisitionError):
                validate_acquisition_plan(plan)

    def test_validation_does_not_read_sealed_reference(self):
        self.reference.unlink()
        validate_acquisition_plan(deepcopy(self.plan))

    def test_candidate_verifier_rejects_unknown_and_postcutoff_records(self):
        records = [json.loads(line) for line in self.corpus.read_text(encoding="utf-8").splitlines()]
        verified, audit = verify_candidates(records, ["a", "missing", "late", "b"], cutoff="2021-08-31")
        self.assertEqual([row["id"] for row in verified], ["a", "b"])
        self.assertEqual(audit, {"requested": 4, "verified": 2, "unknown": 1, "post_cutoff": 1})

    def test_verifier_counterfactual_rejects_exact_unknown_and_postcutoff_injections(self):
        records = [json.loads(line) for line in self.corpus.read_text(encoding="utf-8").splitlines()]
        report = replay_verifier_counterfactual(
            records[:2],
            ["a"],
            cutoff="2021-08-31",
            unknown_candidate_id="counterfactual:unknown",
            postcutoff_record=records[2],
        )
        self.assertEqual(report["injected_candidate_ids"], ["counterfactual:unknown", "late"])
        self.assertEqual(report["unverified_selected_candidate_ids"], ["a", "counterfactual:unknown", "late"])
        self.assertEqual(report["verified_selected_candidate_ids"], ["a"])
        self.assertEqual(report["verification_audit"], {"requested": 3, "verified": 1, "unknown": 1, "post_cutoff": 1})
        self.assertTrue(report["baseline_verified_preserved"])

    def test_embedding_cache_is_bound_to_corpus_and_checkpoint(self):
        cache = {
            "schema_version": "1.0", "seed": 20260820,
            "corpus_sha256": self.plan["case"]["operational_corpus_sha256"],
            "document_checkpoint_sha256": self.checkpoints[0]["document_sha256"],
            "rows": 3, "embedding_sha256": "1" * 64,
        }
        validate_embedding_cache(cache, self.plan, seed=20260820)
        cache["corpus_sha256"] = "2" * 64
        with self.assertRaises(AcquisitionError):
            validate_embedding_cache(cache, self.plan, seed=20260820)

    def test_lock_requires_exact_complete_hash_bound_twelve_slots(self):
        receipts = []
        for slot in self.plan["slots"]:
            output = self.operational / f"{slot['configuration_id']}-{slot['seed']}.json"
            output.write_text(json.dumps({"candidate_ids": ["a"]}), encoding="utf-8")
            receipts.append({
                **slot, "case_id": self.plan["case"]["case_id"], "status": "completed",
                "plan_id": self.plan["plan_id"],
                "corpus_sha256": self.plan["case"]["operational_corpus_sha256"],
                "output_path": str(output), "output_sha256": _sha(output),
            })
        lock = lock_acquisition_outputs(self.plan, receipts)
        self.assertEqual(lock["locked_slots"], 12)
        receipts[-1]["seed"] = 999
        with self.assertRaises(AcquisitionError):
            lock_acquisition_outputs(self.plan, receipts)

    def test_provider_outputs_are_structured_and_ranking_is_deterministic(self):
        queries = parse_query_response('{"queries":["covid antigen test", "diagnostic sensitivity"]}')
        self.assertEqual(queries, ["covid antigen test", "diagnostic sensitivity"])
        candidates = parse_candidate_response('{"candidate_ids":["b", "invented", "a"]}')
        self.assertEqual(candidates, ["b", "invented", "a"])
        self.assertEqual(parse_candidate_response('{"candidate_ids":[]}'), [])
        ranked = rank_candidate_ids(
            [[1.0, 0.0], [0.0, 1.0]],
            [[0.8, 0.1], [0.2, 0.9], [0.8, 0.1]],
            ["a", "b", "c"],
            top_k=3,
        )
        self.assertEqual(ranked, ["b", "a", "c"])
        for invalid in ('{}', '{"queries":[]}', '{"candidate_ids":"a"}'):
            with self.subTest(invalid=invalid), self.assertRaises(AcquisitionError):
                if "queries" in invalid:
                    parse_query_response(invalid)
                else:
                    parse_candidate_response(invalid)

    def test_schema_invalid_candidate_response_becomes_typed_abstention(self):
        self.assertEqual(
            interpret_candidate_response('{}'),
            ([], "abstained_provider_schema_invalid"),
        )
        self.assertEqual(
            interpret_candidate_response('{"candidate_ids":"a"}'),
            ([], "abstained_provider_schema_invalid"),
        )
        self.assertEqual(
            interpret_candidate_response('{"candidate_ids":[]}'),
            ([], "abstained_no_supported_candidate"),
        )
        self.assertEqual(
            interpret_candidate_response('{"candidate_ids":["a"]}'),
            (["a"], "selected"),
        )

    def test_schema_invalid_query_uses_only_frozen_fallback_without_extra_call(self):
        self.assertEqual(
            interpret_query_response('not json', ["frozen q1", "frozen q2"]),
            (["frozen q1", "frozen q2"], "fallback_frozen_generic_query_schema_invalid"),
        )
        self.assertEqual(
            interpret_query_response('{"queries":["model q"]}', ["frozen q"]),
            (["model q"], "generated"),
        )
        with self.assertRaisesRegex(AcquisitionError, "fallback"):
            interpret_query_response('not json', [])

    def test_multiquery_aggregation_has_frozen_diversity_and_consensus_rules(self):
        rankings = [
            ["a", "shared", "c", "d"],
            ["b", "shared", "d", "c"],
        ]
        self.assertEqual(balanced_round_robin(rankings, top_k=4), ["a", "b", "shared", "c"])
        self.assertEqual(reciprocal_rank_fusion(rankings, top_k=3, constant=60)[0], "shared")
        with self.assertRaises(AcquisitionError):
            balanced_round_robin([], top_k=10)

    def test_verifier_counterfactual_uses_delta_when_baseline_already_has_unknown_ids(self):
        records = [{
            "id": "a", "cutoff_verification": {
                "status": "passed", "conservative_latest_date": "2020-06-01"
            }
        }]
        replay = replay_verifier_counterfactual(
            records,
            ["a", "preexisting-hallucination"],
            cutoff="2020-06-07",
            unknown_candidate_id="injected-unknown",
            postcutoff_record={
                "id": "late", "cutoff_verification": {
                    "status": "passed", "conservative_latest_date": "2020-06-08"
                },
            },
        )
        self.assertEqual(replay["baseline_verification_audit"]["unknown"], 1)
        self.assertEqual(replay["verification_audit_delta"]["unknown"], 1)
        self.assertEqual(replay["verification_audit_delta"]["post_cutoff"], 1)
        self.assertTrue(replay["baseline_verified_preserved"])


if __name__ == "__main__":
    unittest.main()
