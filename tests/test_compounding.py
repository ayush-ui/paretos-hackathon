"""Phase 5: as-of curation honesty + lifecycle + contradiction-edge tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate  # noqa: E402


class TestAsOfCurationIsHonest(unittest.TestCase):
    def test_future_belief_not_retired_before_it_exists(self):
        # As of early June, L08 (written 2026-07-21) has not been written -> must NOT be retired yet.
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations(), as_of="2026-06-08")
        self.assertNotEqual(g.beliefs["L08"].status, "retired")

    def test_trap_is_retired_once_evidence_accrues(self):
        # By October (all late-summer weeks observed), the L08 trap must be retired.
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations(), as_of="2026-10-01")
        self.assertEqual(g.beliefs["L08"].status, "retired")

    def test_supersession_only_after_superseder_known(self):
        # As of 2026-08-01, L11 (2026-08-25) is unknown, so L03's window must NOT yet be closed by it.
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations(), as_of="2026-08-01")
        self.assertIsNone(g.beliefs["L03"].valid_to)


class TestContradictionEdge(unittest.TestCase):
    def test_L08_L09_contradiction_detected(self):
        g = curate.build_graph()
        pairs = {(e.src, e.dst) for e in g.edges if e.kind == "contradicts"}
        self.assertIn(("L09", "L08"), pairs)


class TestLiveLoopMatchesHindsight(unittest.TestCase):
    """The fully walk-forward live loop should land close to the hindsight engine (no overfit gap)."""

    def test_live_loop_close_to_static(self):
        from eval.compounding import run_live
        _, live_cost, base_cost = run_live(verbose=False)
        # live re-curated result must still beat the baseline by a wide margin and be near hindsight
        self.assertLess(live_cost, 0.10 * base_cost)        # >90% gap closed
        self.assertLess(live_cost, 18000)                   # within noise of the ~16.3-16.7k hindsight


class TestGraphRenderAsOf(unittest.TestCase):
    def test_render_hides_future_beliefs(self):
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations(), as_of="2026-08-01")
        txt = g.render_text(as_of="2026-08-01")
        self.assertIn("L08", txt)        # written 2026-07-21, visible
        self.assertNotIn("L11", txt)     # written 2026-08-25, hidden


if __name__ == "__main__":
    unittest.main()
