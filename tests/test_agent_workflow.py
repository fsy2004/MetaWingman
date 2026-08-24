from __future__ import annotations

import unittest

from metawingman.agent.poolability_guard import (
    calibrate_guard, safety_score, base_poolability_check)
from metawingman.agent.evpi_director import (
    most_valuable_query, evaluate_living, estimate_evpi, decide_stop)
from metawingman.agent.decision_core import derive_design_decision
from metawingman.agent.graph_search_director import plan_next_search, SearchNode
from metawingman.agent.open_deliberation import deliberate, Candidate
from metawingman.agent.flow_director import run_full_flow, STAGES
from metawingman.training.method_trace_extractor import extract_method_trace
from metawingman.training.expert_judge import judge_process, preference_pairs
from metawingman.training.align_dpo import dpo_loss, preference_alignment
from metawingman.training.method_trace_fidelity import fidelity, aggregate_fidelity


class TestPoolabilityGuard(unittest.TestCase):
    def test_calibrate_picks_threshold_meeting_alpha(self):
        cal = [
            {"comparator_count": 8, "arms_per_study": 3, "outcome_unit": "binary",
             "n_nodes_assessed": True, "is_pooling_misleading": False},
            {"comparator_count": 1, "arms_per_study": 2, "outcome_unit": "continuous",
             "n_nodes_assessed": True, "is_pooling_misleading": False},
            {"comparator_count": 2, "arms_per_study": 2, "outcome_unit": "continuous",
             "n_nodes_assessed": False, "is_pooling_misleading": True},
        ]
        model = calibrate_guard(cal, alpha=0.33)
        self.assertLessEqual(model.empirical_risk, 0.33)
        self.assertEqual(model.calibration_size, 3)

    def test_guard_passes_when_signal_safe(self):
        model = calibrate_guard([
            {"comparator_count": 8, "arms_per_study": 3, "outcome_unit": "binary",
             "n_nodes_assessed": True, "is_pooling_misleading": False},
        ], alpha=0.1)
        guard = model.apply({"comparator_count": 8, "arms_per_study": 3,
                             "outcome_unit": "binary", "n_nodes_assessed": True})
        self.assertTrue(guard.passes)

    def test_non_intervention_designs_not_blocked_by_graph(self):
        guard = base_poolability_check(
            {"exposure_outcome_design": "observational", "outcome_unit": "rate",
             "estimand_aligned": True, "profile_hint": "public_health_exposure"})
        self.assertTrue(guard["graph_connected"])


class TestEvpiDirector(unittest.TestCase):
    def test_most_valuable_query_picks_highest_gain(self):
        q = most_valuable_query([
            {"gap": "a", "expected_utility_gain": 0.4, "uncertainty": 0.5},
            {"gap": "b", "expected_utility_gain": 0.9, "uncertainty": 0.5},
            {"gap": "c", "expected_utility_gain": 0.6, "uncertainty": 0.5},
        ], info_cost=0.1)
        self.assertEqual(q.gap, "b")

    def test_evaluate_living_stops_when_evpi_low(self):
        res = evaluate_living([{"gap": "x", "expected_utility_gain": 0.05,
                               "uncertainty": 0.1}], info_cost=1.0)
        self.assertEqual(res["stop_rule"]["decision"], "stop")
        self.assertFalse(res["living"])

    def test_estimate_evpi_net_of_cost(self):
        self.assertAlmostEqual(estimate_evpi({"expected_utility_gain": 1.0,
                                              "uncertainty": 0.5}, info_cost=0.1), 0.4)


class TestDecisionCore(unittest.TestCase):
    def test_network_case_gets_network_profile_and_passes_guard(self):
        d = derive_design_decision(
            {"type": "intervention", "intervention_count": 8, "is_living_or_update": True},
            {"arms_per_study": 3, "comparator_count": 8, "outcome_unit": "binary",
             "is_update": True, "n_nodes_assessed": True})
        self.assertEqual(d.profile, "intervention_network")
        self.assertTrue(d.risk_guard["passes"])
        self.assertEqual(d.identification_assumption, "nma_consistency")
        self.assertIn(d.identification_assumption, ("nma_consistency", "update_rule"))
        self.assertIn("risk_control", d.risk_guard["guarantee"])
        self.assertIn(d.next_evidence["gap"], ("comparison_graph_coverage", "reference_standard_verification"))

    def test_exposure_case_keeps_exposure_profile(self):
        d = derive_design_decision(
            {"type": "exposure", "is_public_health_exposure": True},
            {"exposure_outcome_design": "observational", "outcome_unit": "rate"})
        self.assertEqual(d.profile, "public_health_exposure")
        self.assertEqual(d.identification_assumption, "observational_adjustment")
        self.assertTrue(d.risk_guard["passes"])


class TestGraphSearch(unittest.TestCase):
    def test_phases_progress_seed_to_expand(self):
        empty = plan_next_search([], landscape={}, seed="depression")
        self.assertEqual(empty.phase, "seed")
        self.assertTrue(empty.queries)
        next_plan = plan_next_search(
            [SearchNode("depression", "pubmed", hits=5, depth=0)],
            landscape={"comparator_count": 1, "n_nodes_assessed": False}, seed="depression")
        self.assertIn(next_plan.phase, ("expand", "snowball"))


class TestOpenDeliberation(unittest.TestCase):
    def test_deliberation_with_two_designs(self):
        d = deliberate(
            {"type": "intervention", "intervention_count": 8},
            {"comparator_count": 8, "outcome_unit": "binary"},
            [Candidate("intervention_network", (), ()),
             Candidate("intervention_pairwise", (), ())])
        self.assertTrue(d.converged)
        self.assertEqual(d.winning_profile, "intervention_network")


class TestFlowDirector(unittest.TestCase):
    def test_full_flow_runs_and_emits_receipt(self):
        flow = run_full_flow(
            {"type": "intervention", "intervention_count": 6, "is_living_or_update": True},
            {"arms_per_study": 3, "comparator_count": 8, "outcome_unit": "continuous",
             "is_update": True, "n_nodes_assessed": True},
            seed="exercise depression")
        self.assertEqual(len(flow["stages"]), len(STAGES))
        self.assertTrue(flow["receipt_sha256"])
        self.assertTrue(flow["step_verification"]["guard_passes"])
        self.assertIn(flow["deliberation"]["winning_profile"],
                      ("intervention_network", "intervention_pairwise", "diagnostic_accuracy",
                       "public_health_exposure", "prognostic_prediction", "prevalence_incidence",
                       "structured_no_pooling", None))


class TestTraining(unittest.TestCase):
    def test_method_trace_strips_outcomes(self):
        record = {
            "case_id": "c1", "review_profile": "intervention_network",
            "method_steps": [{"step": "design_selection", "value": "network"}],
            "final_effect": 0.42, "i2": 0.87, "grade_level": "moderate",
            "effect_direction": "favor",
        }
        trace = extract_method_trace(record)
        self.assertNotIn("final_effect", trace.input_view)
        self.assertNotIn("i2", trace.input_view)
        self.assertEqual(trace.stripped_outcomes["final_effect"], 0.42)
        self.assertTrue(trace.method_trajectory)

    def test_judge_scores_process(self):
        score = judge_process(
            {"decision": {"profile": "intervention_network", "estimand": "e",
                          "synthesis_route": "nma", "risk_guard": {"passes": True,
                          "risk_violation_estimate": 0.02, "alpha": 0.05},
                          "identification_assumption": "nma_consistency",
                          "stop_rule": {"decision": "continue"}}},
            gold_profile="intervention_network")
        self.assertGreater(score.total, 0.5)
        self.assertIn("design_correctness", score.dimensions)

    def test_dpo_loss_smaller_when_chosen_preferred(self):
        preferred = dpo_loss(2.0, 0.5)
        reversed_ = dpo_loss(0.5, 2.0)
        self.assertLess(preferred, reversed_)

    def test_preference_alignment(self):
        pairs = [
            {"chosen_score": 0.9, "rejected_score": 0.2, "chosen": {}, "rejected": {}},
            {"chosen_score": 0.7, "rejected_score": 0.3, "chosen": {}, "rejected": {}},
        ]
        res = preference_alignment(pairs, model_logprobs=[(2.0, 0.5), (1.5, 0.4)])
        self.assertEqual(res["n_pairs"], 2)
        self.assertAlmostEqual(res["win_rate"], 1.0)
        self.assertIsNotNone(res["mean_dpo_loss"])

    def test_fidelity_has_discriminative_power(self):
        gold = {"design_selection": "intervention_network",
                "estimand_identification": "nma_consistency",
                "synthesis_choice": "network meta-analysis",
                "poolable": True, "living_review": True}
        # matching agent trace -> high fidelity
        match = fidelity(
            {"profile": "intervention_network", "identification_assumption": "nma_consistency",
             "synthesis_route": "network meta-analysis", "living": True,
             "risk_guard": {"passes": True}}, gold)
        self.assertGreater(match.total, 0.9)
        # mismatch (wrong design, wrong living, non-poolable claim) -> lower fidelity
        miss = fidelity(
            {"profile": "intervention_pairwise", "identification_assumption": "rct_contrast",
             "synthesis_route": "random-effects pairwise meta-analysis", "living": False,
             "risk_guard": {"passes": False}}, gold)
        self.assertLess(miss.total, match.total)
        self.assertLess(miss.total, 0.8)

    def test_aggregate_fidelity(self):
        gold = {"design_selection": "intervention_network", "estimand_identification": "nma_consistency",
                "synthesis_choice": "network meta-analysis", "poolable": True, "living_review": True}
        agg = aggregate_fidelity([
            {"profile": "intervention_network", "identification_assumption": "nma_consistency",
             "synthesis_route": "network meta-analysis", "living": True, "risk_guard": {"passes": True}},
            {"profile": "intervention_pairwise", "identification_assumption": "rct_contrast",
             "synthesis_route": "random-effects pairwise meta-analysis", "living": False,
             "risk_guard": {"passes": False}},
        ], [gold, gold])
        self.assertEqual(agg["n"], 2)
        self.assertGreater(agg["mean_fidelity"], 0.0)
        self.assertLessEqual(agg["mean_fidelity"], 1.0)


if __name__ == "__main__":
    unittest.main()
