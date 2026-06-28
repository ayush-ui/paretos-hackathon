"""Regression guards on the SCORED (deterministic hint) path — the golden baselines the merge must
never silently regress. Numbers verified 2026-06-28 (see docs/MERGE_PLAN.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from eval.backtest import run, make_ew_ratio  # noqa: E402
from eval.oos import run_oos  # noqa: E402


class TestGoldenBaselines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        g = curate.build_graph()  # use_llm=False: the scored default
        curate.curate(g, data.load_present(), data.load_recommendations())
        cls.engine = predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4)

    def test_training_gap_locked(self):
        res = run(self.engine.as_strategy())
        # locked at 93.03%; allow only downward-protective drift guard
        self.assertAlmostEqual(res["gap_closed_pct"], 93.03, delta=0.2)
        self.assertGreater(res["gap_closed_pct"], run(make_ew_ratio(14))["gap_closed_pct"])

    def test_sep_oos_locked(self):
        r = run_oos(cutoff="2026-09-01", use_llm=False)
        self.assertEqual(r["n_days"], 22)
        self.assertAlmostEqual(r["gap_closed_pct"], 95.0, delta=0.5)

    def test_sep_oos_beats_flat_trim(self):
        # the OOS engine must beat a naive flat-17% on the same frozen window
        r = run_oos(cutoff="2026-09-01", use_llm=False)
        self.assertGreater(r["gap_closed_pct"], 92.0)


class TestTrendBeliefRecognisedForOctober(unittest.TestCase):
    def test_trend_active_from_log(self):
        # L14/L15 (autumn ramp) must switch the trend lead on for the holdout — regardless of whether
        # they are labelled 'note' or 'trend'. Guards the kind-label robustness fix.
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations())
        eng = predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4)
        self.assertTrue(eng._trend_active)


if __name__ == "__main__":
    unittest.main()
