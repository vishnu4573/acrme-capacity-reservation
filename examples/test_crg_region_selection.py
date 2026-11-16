"""Local advisory-selector tests; no Azure calls or programme POC claims."""

import unittest
from dataclasses import replace
from datetime import timedelta

from crg_region_selection import FACTORS, demo_inputs, select_region


class RegionSelectionTests(unittest.TestCase):
    def setUp(self):
        self.request, self.candidates, self.weights, self.now = demo_inputs()

    def select(self, request=None, candidates=None, weights=None):
        return select_region(
            request if request is not None else self.request,
            candidates if candidates is not None else self.candidates,
            weights if weights is not None else self.weights,
            self.now, timedelta(minutes=5),
        )

    def test_scoring_and_capacity_gate(self):
        decision = self.select()
        self.assertEqual(decision.region, "eastus2")
        self.assertAlmostEqual(decision.ranked[0][1], 0.8)
        self.assertAlmostEqual(decision.ranked[1][1], 0.7625)
        self.assertIn("demo-westus2", decision.rejected)

    def test_default_prod_requires_exact_region(self):
        with self.assertRaises(ValueError):
            self.select(request=replace(self.request, geography_exception_approved=False))
        with self.assertRaises(ValueError):
            self.select(request=replace(self.request, customer_acknowledged=False))

    def test_fixed_region_never_moves_even_when_blocked(self):
        request = replace(self.request, fixed_region="westus2")
        decision = self.select(request=request)
        self.assertEqual(decision.status, "BLOCKED")
        self.assertEqual(decision.region, "westus2")
        self.assertIsNone(decision.crg_id)
        self.assertEqual(self.select(request=replace(request, fixed_region="centralus")).region,
                         "centralus")

    def test_gates_cannot_be_bypassed_by_score(self):
        original = self.candidates[0]
        changes = (
            {"vm_size": "Standard_D8s_v5"}, {"zone": "2"},
            {"geography": "Europe"}, {"domain": "WMS"},
            {"environment": "CVAL"}, {"subscription_id": "other-sub"},
            {"available_instances": -1}, {"standard_region": False},
            {"reservation_supported": False}, {"family_quota_admitted": False},
            {"regional_quota_admitted": False}, {"snapshot_id": ""},
            {"observed_at": self.now - timedelta(minutes=6)},
            {"observed_at": self.now + timedelta(seconds=1)},
            {"observed_at": self.now.replace(tzinfo=None)},
            {"hard_constraints": {}},
            {"hard_constraints": dict(original.hard_constraints, **{"HC-6": "FAIL"})},
            {"normalized_factors": {}},
            {"normalized_factors": dict(original.normalized_factors, quota=float("nan"))},
            {"environment_customers": 11}, {"geography_customers": -1},
        )
        for change in changes:
            with self.subTest(change=change):
                self.assertEqual(self.select(candidates=[replace(original, **change)]).status,
                                 "BLOCKED")

    def test_zero_customer_fairness_and_deterministic_ties(self):
        candidate = replace(self.candidates[0], geography_customers=0, environment_customers=0)
        decision = self.select(candidates=[candidate])
        self.assertAlmostEqual(decision.ranked[0][1], 0.825)
        tied = replace(candidate, crg_id="demo-centralus", region="centralus")
        self.assertEqual(self.select(candidates=[candidate, tied]).region, "centralus")
        self.assertEqual(self.select(candidates=[tied, candidate]).region, "centralus")

    def test_invalid_weights_and_request(self):
        for weights in ({}, {factor: 1.0 for factor in FACTORS},
                        dict(self.weights, quota=float("nan")),
                        dict(self.weights, quota=-0.125)):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                self.select(weights=weights)
        for count in (0, -1, 1.5, True):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.select(request=replace(self.request, count=count))
        with self.assertRaises(ValueError):
            self.select(candidates=[self.candidates[0], self.candidates[0]])
        self.assertEqual(self.select(candidates=[]).status, "BLOCKED")


if __name__ == "__main__":
    unittest.main()