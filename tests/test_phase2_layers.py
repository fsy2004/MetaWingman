from __future__ import annotations

import unittest

from metawingman.agent.design_search import generate_candidates, search
from metawingman.agent.error_taxonomy import classify
from metawingman.agent.novelty_gate import gate, executability_score
from metawingman.agent.step_compliance import check_flow


class TestDesignSearch(unittest.TestCase):
    def test_candidates_and_prune(self):
        sig = {"has_reference_standard": True, "comparator_count": 0, "outcome_measure_type": "diagnostic"}
        cands = generate_candidates("diagnostic_accuracy", sig)
        self.assertIn("diagnostic_accuracy", cands)
        node = search(sig, "diagnostic_accuracy", gold=None)
        self.assertEqual(node.score, 1.0)  # full evidence support


class TestErrorTaxonomy(unittest.TestCase):
    def test_label_proxy_classification(self):
        attrs = classify({"gold_profile": "prevalence_incidence",
                          "agent_profile": "prevalence_incidence",
                          "gold_poolable": False, "agent_poolable": True,
                          "dimensions": {"design_selection": 1.0, "guard_consistency": 0.0}})
        self.assertTrue(any(a.kind == "label_proxy_nonpooling" for a in attrs))


class TestNoveltyGate(unittest.TestCase):
    def test_gate_reject_when_covered(self):
        res = gate(["a", "b"], {"a": 5, "b": 7, "c": 0},
                   {"comparator_count": 2, "outcome_measure_type": "binary",
                    "precedent_found": True, "evidence_actions": 3}, public_anchor=True)
        # fully covered topic: novelty low -> reject
        self.assertIn(res.decision, ("reject", "review"))
        self.assertLess(res.novelty, 5.0)

    def test_executability_score_uses_only_objective_evidence(self):
        score, fails = executability_score({"comparator_count": 2}, public_anchor=True)
        self.assertGreaterEqual(score, 5.0)


class TestStepCompliance(unittest.TestCase):
    def test_full_flow_ok(self):
        cert = {"primitives": "p", "hypothesis": "h", "falsifier": "f",
                "mechanism_model": "m", "minimal_decisive_test": "d", "failure_update": "u"}
        res = check_flow(cert,
                         {"profile": "diagnostic_accuracy",
                          "identification_assumption": "reference_standard",
                          "synthesis_route": "bivariate"},
                         {"passes": True, "guarantee": "risk_control", "alpha": 0.1},
                         {"living": False, "stop_rule": {"decision": "stop"}})
        self.assertEqual(res["full_flow_rate"], 1.0)
        self.assertEqual(res["per_stage_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
