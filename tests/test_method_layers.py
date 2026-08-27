from __future__ import annotations

import unittest

from metawingman.agent.budget_allocator import allocate
from metawingman.agent.debate_director import debate
from metawingman.agent.precedent_store import PrecedentStore
from metawingman.agent.question_certificate import build_certificate, gate
from metawingman.agent.risk_controller import RiskController


class TestQuestionCertificate(unittest.TestCase):
    def test_certificate_complete_and_gate_ok(self):
        cert = build_certificate(
            {"type": "diagnostic", "has_index_test_reference": True},
            {"has_reference_standard": True, "outcome_unit": "diagnostic"},
            {"profile": "diagnostic_accuracy", "estimand": "sens/spec",
             "decision_tension": "t", "minimal_decisive_question": "m",
             "risk_guard": {"passes": True}})
        g = gate(cert)
        self.assertTrue(g["passed"])
        self.assertGreaterEqual(cert.quality_scores["falsifiability"], 3.0)

    def test_empty_falsifier_fails_hard_gate(self):
        cert = build_certificate(
            {"type": "intervention", "intervention_count": 2},
            {"comparator_count": 2, "outcome_unit": "binary"}, {})
        cert_f = cert.__class__(**{**cert.__dict__, "falsifier": ""})
        self.assertIn("falsifier_empty", gate(cert_f)["failed_hard"])


class TestRiskController(unittest.TestCase):
    def test_three_actions_by_risk(self):
        rc = RiskController(tau_accept=0.10)
        self.assertEqual(rc.apply({"safety_score": 0.05, "passes": True}).action, "accept")
        self.assertEqual(rc.apply({"safety_score": 0.14, "passes": False}).action, "audit")
        self.assertEqual(rc.apply({"safety_score": 0.60, "passes": False}).action, "abstain")


class TestDebate(unittest.TestCase):
    def test_debate_verdict_and_swap(self):
        d = debate({"comparator_count": 10, "arms_per_study": 4},
                   {"profile": "intervention_pairwise", "risk_guard": {"passes": True}})
        self.assertEqual(d.verdict, "reject")          # oppose evidence > support
        self.assertIn(d.stance_a, ("support",))
        d2 = debate({"has_reference_standard": True, "comparator_count": 0},
                    {"profile": "diagnostic_accuracy", "risk_guard": {"passes": True}})
        self.assertIn(d2.verdict, ("support", "suspend"))


class TestPrecedentStore(unittest.TestCase):
    def test_capacity_and_retrieval(self):
        store = PrecedentStore(capacity=4)
        for i in range(6):
            store.register({"comparator_count": i + 1}, "intervention_pairwise", True, False)
        self.assertEqual(len(store), 4)  # bounded memory
        hits = store.retrieve({"comparator_count": 3})
        self.assertTrue(hits)


class TestBudgetAllocator(unittest.TestCase):
    def test_monotone_in_risk(self):
        a1 = allocate(0.05)
        a2 = allocate(0.15)
        a3 = allocate(0.30)
        self.assertLess(a1["evidence_actions"], a2["evidence_actions"])
        self.assertLessEqual(a2["evidence_actions"], a3["evidence_actions"])


if __name__ == "__main__":
    unittest.main()
