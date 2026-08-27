from __future__ import annotations

import unittest

from metawingman.agent.novelty_gate import gate
from metawingman.agent.topic_discovery import bigrams, build_functional_terms, tokens


class TestTopicDiscovery(unittest.TestCase):
    def test_bigrams_and_terms(self):
        self.assertIn("rapid_antigen", bigrams(["rapid", "antigen", "diagnostics"]))
        terms = build_functional_terms([{"title": "rapid antigen diagnostics covid"}], {"covid"})
        self.assertIn("rapid", terms)

    def test_gate_novelty_override(self):
        res = gate(["rapid", "antigen"], {}, {"comparator_count": 0, "precedent_found": True,
                                              "evidence_actions": 4}, public_anchor=True,
                   novelty_override=8.0)
        self.assertEqual(res.decision, "select")
        self.assertEqual(res.novelty, 8.0)


if __name__ == "__main__":
    unittest.main()
