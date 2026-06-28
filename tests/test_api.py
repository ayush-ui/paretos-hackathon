"""API endpoint tests via FastAPI TestClient. Covers the contract + an anti-leakage check.

(The slow endpoints /api/compounding and /api/validation reuse logic already covered by the eval
tests; they're smoke-checked here only for wiring to keep this suite fast.)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)


class TestApi(unittest.TestCase):
    def test_health(self):
        self.assertEqual(client.get("/api/health").json()["status"], "ok")

    def test_summary_engine_beats_b2(self):
        s = client.get("/api/summary").json()
        self.assertLess(s["engine_cost"], s["b2_adaptive_cost"])
        self.assertGreater(s["engine_gap_closed_pct"], 92.0)
        self.assertEqual(s["baseline_cost"], 234600)

    def test_cycles(self):
        rows = client.get("/api/cycles").json()
        self.assertEqual(len(rows), 20)  # 20 training decision weeks
        self.assertIn("gap_closed_pct", rows[0])

    def test_current_plan_is_holdout_and_leak_free(self):
        rows = client.get("/api/plan/current").json()
        self.assertEqual(len(rows), 20)  # 4 holdout weeks x 5 working days
        for r in rows:
            self.assertGreaterEqual(r["date"], "2026-10-01")  # all October
            self.assertLess(r["planned"], r["recommended"])   # we trim the optimiser

    def test_trace_training_day_has_outcome(self):
        t = client.get("/api/plan/2026-09-07/trace").json()
        self.assertFalse(t["is_holdout"])
        self.assertIsNotNone(t["actual"])
        self.assertIn("k", t)
        self.assertTrue(t["reason_text"])

    def test_trace_holdout_day_hides_actual(self):
        t = client.get("/api/plan/2026-10-05/trace").json()
        self.assertTrue(t["is_holdout"])
        self.assertIsNone(t["actual"])          # anti-leakage: no holdout outcome exposed
        self.assertIsNone(t["our_cost"])

    def test_trace_unknown_date_404(self):
        self.assertEqual(client.get("/api/plan/2030-01-01/trace").status_code, 404)

    def test_staffing_series(self):
        rows = client.get("/api/staffing").json()
        self.assertTrue(len(rows) >= 20)
        # training weeks carry an actual; holdout weeks omit it (anti-leakage)
        train = [r for r in rows if not r["is_holdout"]]
        holdout = [r for r in rows if r["is_holdout"]]
        self.assertTrue(train and holdout)
        self.assertIsNotNone(train[0]["actual_pd"])
        self.assertIsNone(holdout[0]["actual_pd"])
        # we trim: planned person-days sit below the optimiser's recommendation
        self.assertLess(holdout[0]["planned_pd"], holdout[0]["optimiser_pd"])

    def test_graph_endstate(self):
        g = client.get("/api/graph").json()
        ids = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(ids["L08"]["status"], "retired")
        self.assertTrue(any(e["kind"] == "contradicts" for e in g["edges"]))

    def test_graph_as_of_hides_future(self):
        g = client.get("/api/graph", params={"as_of": "2026-08-01"}).json()
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("L08", ids)       # written 2026-07-21
        self.assertNotIn("L11", ids)    # written 2026-08-25, future

    def test_belief_detail(self):
        b = client.get("/api/beliefs/L11").json()
        self.assertEqual(b["id"], "L11")
        self.assertIn("Picking", b["activities"])
        self.assertGreater(b["contribution_eur"], 0)  # pick-by-light belief pays off

    def test_belief_404(self):
        self.assertEqual(client.get("/api/beliefs/ZZZ").status_code, 404)


if __name__ == "__main__":
    unittest.main()
