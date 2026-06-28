"""Provenance KG tests — ontology, walk-forward honesty, trace shape, API wiring.

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

NODE_TYPES = {"source", "belief", "decision", "outcome"}
EDGE_TYPES = {"SOURCED_FROM", "INFORMED", "CONSIDERED", "RESULTED_IN", "UPDATED",
              "PRECEDED", "CONTRADICTS"}


class TestProvenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = get_state().provenance()

    def test_ontology_node_and_edge_types(self):
        types = {n["type"] for n in self.snap["nodes"]}
        self.assertTrue(types.issubset(NODE_TYPES))
        self.assertEqual(types, NODE_TYPES)  # all four ontology node kinds present
        etypes = {e["type"] for e in self.snap["edges"]}
        self.assertTrue(etypes.issubset(EDGE_TYPES))
        # the core compounding edges must exist
        for required in ("SOURCED_FROM", "INFORMED", "RESULTED_IN", "PRECEDED"):
            self.assertIn(required, etypes)

    def test_every_belief_has_a_source(self):
        belief_ids = {n["id"] for n in self.snap["nodes"] if n["type"] == "belief"}
        sourced = {e["src"] for e in self.snap["edges"] if e["type"] == "SOURCED_FROM"}
        self.assertTrue(belief_ids.issubset(sourced), "a belief node has no SOURCED_FROM edge")

    def test_each_decision_resulted_in_one_outcome(self):
        decisions = [n for n in self.snap["nodes"] if n["type"] == "decision"]
        ri = [e for e in self.snap["edges"] if e["type"] == "RESULTED_IN"]
        self.assertEqual(len(decisions), len(ri))

    def test_edges_reference_existing_nodes(self):
        ids = {n["id"] for n in self.snap["nodes"]}
        for e in self.snap["edges"]:
            self.assertIn(e["src"], ids)
            self.assertIn(e["dst"], ids)

    def test_as_of_is_walk_forward_honest(self):
        cut = "2026-07-01"
        snap = get_state().provenance(as_of=cut)
        # no decision/outcome week, and no belief, may post-date the cutoff
        for n in snap["nodes"]:
            if n["type"] in ("decision", "outcome"):
                self.assertLess(n["week"], cut)
            if n["type"] == "belief":
                self.assertLess(n["valid_from"], cut)
        # strictly fewer nodes than the full graph
        self.assertLess(len(snap["nodes"]), len(self.snap["nodes"]))

    def test_trace_chain(self):
        weeks = sorted(n["week"] for n in self.snap["nodes"] if n["type"] == "decision")
        t = get_state().provenance_trace(weeks[5])
        self.assertIsNotNone(t)
        self.assertIn("informed_by", t)
        self.assertIsNotNone(t["outcome"])

    # --- API wiring -----------------------------------------------------------------------
    def test_api_provenance(self):
        r = client.get("/api/provenance").json()
        self.assertIn("nodes", r)
        self.assertIn("edges", r)
        self.assertEqual({n["type"] for n in r["nodes"]}, NODE_TYPES)

    def test_api_trace_404(self):
        self.assertEqual(client.get("/api/provenance/1999-01-01/trace").status_code, 404)


if __name__ == "__main__":
    unittest.main()
