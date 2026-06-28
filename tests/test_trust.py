"""Shadow-trust trajectory tests — EWMA shape, walk-forward honesty, the L08-trap decay, API wiring.

Uses the shared AppState singleton so the (slow) walk-forward build happens once per test process.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402
from api.state import get_state  # noqa: E402

client = TestClient(app)


class TestTrustTrajectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = get_state().trust_trajectory()
        cls.traj = cls.out["trajectories"]

    def test_ewma_recurrence_holds(self):
        # every point must satisfy trust_w = 0.6*trust_{w-1} + 0.4*helped
        a = self.out["params"]["alpha"]
        init = self.out["params"]["init_trust"]
        for pts in self.traj.values():
            prev = init
            for p in pts:
                expected = (1 - a) * prev + a * p["helped"]
                self.assertAlmostEqual(p["trust"], expected, places=3)
                prev = p["trust"]

    def test_trust_bounded(self):
        for pts in self.traj.values():
            for p in pts:
                self.assertGreaterEqual(p["trust"], 0.0)
                self.assertLessEqual(p["trust"], 1.0)
                self.assertIn(p["helped"], (0.0, 0.5, 1.0))

    def test_l08_trap_loses_trust(self):
        # the L08 'cut 15%' trap must decay toward 0 as evidence accrues (the curation story, shadowed)
        l08 = self.traj.get("L08")
        self.assertIsNotNone(l08)
        self.assertLess(l08[-1]["trust"], 0.1)
        self.assertLess(l08[-1]["trust"], l08[0]["trust"])  # strictly decayed

    def test_curve_starts_when_belief_captured(self):
        # a belief's first trajectory week must be on/after its capture (no pre-history, walk-forward)
        from src import beliefs
        caps = {b.id: b.valid_from for b in beliefs.ingest_decision_log()}
        for bid, pts in self.traj.items():
            if bid in caps:
                self.assertGreaterEqual(pts[0]["week"], caps[bid][:7])  # same month or later

    def test_api_trust(self):
        r = client.get("/api/trust").json()
        self.assertIn("trajectories", r)
        self.assertIn("summary", r)
        self.assertEqual(r["params"]["alpha"], 0.4)


if __name__ == "__main__":
    unittest.main()
