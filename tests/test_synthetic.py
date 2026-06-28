"""Synthetic stress-test guards (eval/synthetic_stress.py).

SYNTHETIC evidence: the harness re-implements the teammate's regime-world generator on OUR data +
cost function and runs the frozen engine vs the no-knowledge ablation. The thesis claim we pin: on
a learnable rising-demand regime (the autumn ramp), the belief/trend knowledge layer helps — our
engine must beat the ablation. We do NOT pin the unseen-shock worlds (heat/flu): the engine has no
belief for them, so being neutral/slightly worse there is honest, not a regression.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import synthetic_stress as ss  # noqa: E402


class TestSyntheticStress(unittest.TestCase):
    def test_runs_all_worlds_deterministically(self):
        r1 = ss.run_all(seed=7)
        r2 = ss.run_all(seed=7)
        self.assertEqual(len(r1), len(ss.WORLDS))
        # deterministic given the seed
        self.assertEqual([x["engine_cost"] for x in r1], [x["engine_cost"] for x in r2])
        for row in r1:
            self.assertGreater(row["n_days"], 0)
            self.assertIn("provenance", row)

    def test_engine_beats_ablation_on_ramp(self):
        r = ss.run_world("autumn ramp", ss.WORLDS["autumn ramp"], seed=7)
        # the trend/belief layer must add value on a rising-demand regime
        self.assertTrue(r["engine_beats_naive"],
                        f"engine €{r['engine_cost']:.0f} should beat ablation €{r['naive_cost']:.0f}")
        self.assertLess(r["engine_cost"], r["naive_cost"])

    def test_generator_grounded_and_bounded(self):
        # synthetic need stays non-negative and is shaped by the optimiser recs (not random noise)
        import datetime as _dt
        dates = ["2026-10-05", "2026-10-06", "2026-10-07"]
        opt = {d: 70.0 for d in dates}
        need, prov = ss.generate(dates, opt, ss.WORLDS["autumn ramp"], seed=7)
        self.assertEqual(set(need), set(dates))
        for v in need.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLess(v, 70.0)  # base_rate 0.837 + small noise stays below the optimiser rec
        self.assertTrue(any("0.837" in p[1] for p in prov))


class TestSyntheticApi(unittest.TestCase):
    def test_api_synthetic_shape(self):
        from fastapi.testclient import TestClient
        from api.main import app
        r = TestClient(app).get("/api/synthetic").json()
        self.assertIn("worlds", r)
        self.assertIn("note", r)
        self.assertEqual(len(r["worlds"]), len(ss.WORLDS))
        w = r["worlds"][0]
        for key in ("world", "engine_gap_pct", "naive_gap_pct", "engine_beats_naive"):
            self.assertIn(key, w)


if __name__ == "__main__":
    unittest.main()
