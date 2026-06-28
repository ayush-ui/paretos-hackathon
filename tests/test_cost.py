"""Unit tests pinning the cost function — especially the asymmetry and the 2.0 SLA boundary.

Run: python3 -m pytest tests/ -q   (or: python3 -m unittest discover -s tests)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cost import (  # noqa: E402
    day_cost, score_plan, gap_closed_pct, cost_breakdown,
    IDLE_COST_PER_PERSON_DAY, OVERTIME_COST_PER_PERSON_DAY, SLA_PENALTY_PER_PERSON_DAY,
)


class TestDayCost(unittest.TestCase):
    def test_perfect_is_zero(self):
        self.assertEqual(day_cost(50.0, 50.0), 0.0)

    def test_overstaff_is_idle_rate(self):
        self.assertAlmostEqual(day_cost(53.0, 50.0), 3.0 * IDLE_COST_PER_PERSON_DAY)

    def test_understaff_within_tolerance_is_premium_only(self):
        # 1.5 short, below the 2.0 SLA tolerance -> premium only, no penalty
        self.assertAlmostEqual(day_cost(48.5, 50.0), 1.5 * OVERTIME_COST_PER_PERSON_DAY)

    def test_understaff_exactly_at_tolerance_no_penalty(self):
        # exactly 2.0 short: condition is strict (> 2.0), so no SLA penalty yet
        self.assertAlmostEqual(day_cost(48.0, 50.0), 2.0 * OVERTIME_COST_PER_PERSON_DAY)

    def test_understaff_beyond_tolerance_adds_penalty(self):
        # 3.0 short: premium on all 3 + penalty on the 1.0 beyond tolerance
        expected = 3.0 * OVERTIME_COST_PER_PERSON_DAY + 1.0 * SLA_PENALTY_PER_PERSON_DAY
        self.assertAlmostEqual(day_cost(47.0, 50.0), expected)

    def test_asymmetry_small_undershoot_cheaper_than_safe_overshoot(self):
        # The core lesson: a 2.0 undershoot beats a 2.0 overshoot.
        self.assertLess(day_cost(48.0, 50.0), day_cost(52.0, 50.0))

    def test_penalty_makes_big_undershoot_explode(self):
        # But a 5.0 undershoot is far worse than a 5.0 overshoot once SLA detonates.
        self.assertGreater(day_cost(45.0, 50.0), day_cost(55.0, 50.0))

    def test_never_negative(self):
        for plan in (0.0, 49.9, 50.0, 50.1, 100.0):
            self.assertGreaterEqual(day_cost(plan, 50.0), 0.0)


class TestScorers(unittest.TestCase):
    def test_score_plan_sums_days(self):
        need = {"d1": 50.0, "d2": 50.0}
        plan = {"d1": 53.0, "d2": 48.0}
        expected = 3.0 * IDLE_COST_PER_PERSON_DAY + 2.0 * OVERTIME_COST_PER_PERSON_DAY
        self.assertAlmostEqual(score_plan(plan, need), expected)

    def test_score_plan_missing_date_raises(self):
        with self.assertRaises(KeyError):
            score_plan({"d1": 50.0}, {"d1": 50.0, "d2": 50.0})

    def test_gap_closed(self):
        self.assertAlmostEqual(gap_closed_pct(0.0, 1000.0), 100.0)
        self.assertAlmostEqual(gap_closed_pct(1000.0, 1000.0), 0.0)
        self.assertAlmostEqual(gap_closed_pct(500.0, 1000.0), 50.0)
        self.assertEqual(gap_closed_pct(10.0, 0.0), 0.0)  # degenerate baseline

    def test_breakdown_components_sum_to_total(self):
        need = {"d1": 50.0, "d2": 50.0, "d3": 50.0}
        plan = {"d1": 53.0, "d2": 48.0, "d3": 45.0}
        b = cost_breakdown(plan, need)
        self.assertAlmostEqual(
            b["total"], b["overstaff_cost"] + b["understaff_premium_cost"] + b["sla_penalty_cost"]
        )
        self.assertAlmostEqual(b["total"], score_plan(plan, need))


if __name__ == "__main__":
    unittest.main()
