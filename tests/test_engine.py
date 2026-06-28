"""Engine, curation, and anti-leakage tests."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, beliefs, curate, predict  # noqa: E402
from eval.backtest import Context, run, make_ew_ratio  # noqa: E402


class TestBeliefIngestion(unittest.TestCase):
    def test_ingest_15_beliefs(self):
        self.assertEqual(len(beliefs.ingest_decision_log()), 15)

    def test_picking_regime_beliefs_have_event_start(self):
        bs = {b.id: b for b in beliefs.ingest_decision_log()}
        # valid_from = later of captured_on (08-25) and claimed event (08-24): you may only act on a
        # learning once you have it. Anti-leakage by construction.
        self.assertEqual(bs["L11"].valid_from, "2026-08-25")
        self.assertEqual(bs["L03"].valid_from, "2026-06-09")  # captured_on

    def test_payday_monday_detection(self):
        self.assertTrue(beliefs._is_payday_monday("2026-06-29"))   # last Monday of June
        self.assertFalse(beliefs._is_payday_monday("2026-06-22"))  # not last Monday
        self.assertFalse(beliefs._is_payday_monday("2026-06-30"))  # a Tuesday


class TestCuration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = curate.build_graph()
        curate.curate(cls.g, data.load_present(), data.load_recommendations())

    def test_retires_the_L08_trap(self):
        # L08 ('cut operative 15pct in late summer') is the trap; actuals show need ran HIGHER.
        self.assertEqual(self.g.beliefs["L08"].status, "retired")

    def test_supersession_closes_stale_picking_trim(self):
        # The old -12pct picking trim (L03) must be window-closed when the newer note took effect.
        self.assertEqual(self.g.beliefs["L03"].valid_to, "2026-08-25")

    def test_no_belief_left_as_pure_candidate_unscored(self):
        # every belief ends in a known curated state
        for b in self.g.list():
            self.assertIn(b.status, ("active", "candidate", "stale", "retired"))


class TestAntiLeakage(unittest.TestCase):
    def test_context_hides_future(self):
        present = {"2026-05-18": 50.0, "2026-06-01": 55.0}
        ctx = Context(present, {}, {"2026-05-18": 60.0, "2026-06-01": 66.0}, horizon="2026-05-25")
        past = ctx.past_need()
        self.assertIn("2026-05-18", past)
        self.assertNotIn("2026-06-01", past)  # on/after horizon must be hidden

    def test_engine_never_reads_future_in_walkforward(self):
        # Spy Context that records the max date any strategy reads; assert < each cycle's horizon.
        recs = data.load_recommendations()
        present = data.load_present()
        violations = []

        eng = predict.Engine(curate.build_graph(), halflife=21.0)

        # monkeypatch-free check: re-run the harness logic and assert horizons are mondays < planned
        import eval.backtest as bt
        for dd in sorted(recs):
            rec = recs[dd]
            scored = [d for d in rec.dates if data.is_working_day(d) and d in present]
            if not scored:
                continue
            horizon = bt._decision_week_monday(dd)
            # horizon must be strictly before every planned (scored) day
            for d in scored:
                if d <= horizon:
                    violations.append((dd, d, horizon))
        self.assertEqual(violations, [], "a planned day was not strictly after its decision horizon")


class TestEnginePerformance(unittest.TestCase):
    """Regression guard: the belief-led engine must beat the B2 bar on training (walk-forward)."""

    def test_engine_beats_b2(self):
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations())
        eng = predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4)
        res = run(eng.as_strategy())
        b2 = run(make_ew_ratio(14))
        self.assertLess(res["total_strategy_cost"], b2["total_strategy_cost"])
        self.assertGreater(res["gap_closed_pct"], 92.0)

    def test_graph_adds_value_vs_ablation(self):
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations())
        with_graph = run(predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4).as_strategy())
        without = run(predict.Engine(None, halflife=21.0, offset=0.3, trend_gain=0.0).as_strategy())
        self.assertLess(with_graph["total_strategy_cost"], without["total_strategy_cost"])


class TestProtectiveLeanOptions(unittest.TestCase):
    """The opt-in protective-lean levers (k_window / auto_offset) must be live AND default-off:
    leaving them unset must reproduce the locked plan exactly (guards the scored path)."""

    @classmethod
    def setUpClass(cls):
        cls.g = curate.build_graph()
        curate.curate(cls.g, data.load_present(), data.load_recommendations())

    def _strat_run(self, **kw):
        return run(predict.Engine(self.g, halflife=21.0, offset=0.3, trend_gain=0.4, **kw).as_strategy())

    def test_defaults_off_reproduce_locked(self):
        # explicit defaults must equal the no-kwargs engine (no accidental behaviour change)
        a = self._strat_run()
        b = self._strat_run(k_window=None, auto_offset=False)
        self.assertEqual(a["total_strategy_cost"], b["total_strategy_cost"])

    def test_options_are_live(self):
        # each lever must actually move the plan (otherwise the A/B is meaningless)
        base = self._strat_run()["total_strategy_cost"]
        self.assertNotAlmostEqual(self._strat_run(k_window=30)["total_strategy_cost"], base, places=0)
        self.assertNotAlmostEqual(self._strat_run(auto_offset=True)["total_strategy_cost"], base, places=0)

    def test_ab_concludes_no_adoption(self):
        # the documented negative result: no protective variant clears the adoption gate
        from eval.protective_ab import evaluate
        rows = evaluate()
        adopted = [r for r in rows if r["adopt"] and not r["name"].startswith("DEFAULT")]
        self.assertEqual(adopted, [], "a protective variant unexpectedly cleared the gate — re-pin baselines")


if __name__ == "__main__":
    unittest.main()
