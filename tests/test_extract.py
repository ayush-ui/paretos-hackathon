"""LLM-first extraction + deterministic-fallback tests.

These never call the network: the fallback path needs no key, and the LLM path is exercised through
the committed, reviewed cache (state/belief_extractions.json) whose entries are 'fresh' so no call
is made. This is exactly the determinism contract — a reviewed cache is a frozen, reproducible input.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import beliefs, curate, extract  # noqa: E402


class TestDeterministicFallback(unittest.TestCase):
    def test_fallback_matches_hint_ingestion_exactly(self):
        # use_llm=False must reproduce the original hint-based beliefs, ignoring any cache on disk.
        bs, edges = extract.extracted_beliefs(use_llm=False)
        hint = beliefs.ingest_decision_log()
        self.assertEqual(len(bs), len(hint))
        for a, b in zip(sorted(bs, key=lambda x: x.id), sorted(hint, key=lambda x: x.id)):
            self.assertEqual(a.id, b.id)
            self.assertEqual(a.kind, b.kind)
            self.assertEqual(a.params, b.params)
            self.assertEqual(a.valid_from, b.valid_from)
        self.assertEqual(edges, [])  # no LLM edges on the fallback path

    def test_fallback_ignores_cache_even_when_present(self):
        # cache exists, but use_llm=False must not read it
        if os.path.exists(extract.CACHE_PATH):
            bs, edges = extract.extracted_beliefs(use_llm=False)
            # L09 in the hint path is a plain note with no contradicts edge
            self.assertEqual(edges, [])


class TestLlmCachePath(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(extract.CACHE_PATH), "no reviewed extraction cache committed")
    def test_cache_path_is_deterministic_and_makes_no_call(self):
        # all entries fresh => no key needed; relationships the LLM caught should appear as edges
        bs, edges = extract.extracted_beliefs(use_llm=True)
        self.assertEqual(len(bs), 15)
        kinds = {(e.src, e.dst, e.kind) for e in edges}
        self.assertIn(("L09", "L08", "contradicts"), kinds)   # heat dispute captured from prose
        self.assertIn(("L11", "L03", "supersedes"), kinds)    # pick-by-light retires the old trim

    @unittest.skipUnless(os.path.exists(extract.CACHE_PATH), "no reviewed extraction cache committed")
    def test_llm_graph_builds_and_curates(self):
        g = curate.build_graph(use_llm=True)
        self.assertEqual(len(g.beliefs), 15)


class TestMissCacheToTempFallsBack(unittest.TestCase):
    def test_empty_cache_dir_falls_back_to_hint_without_key(self):
        # empty cache + LLM 'unavailable' (simulated) => every note falls back to the hint, no call
        orig = extract.llm.available
        extract.llm.available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as d:
                empty = os.path.join(d, "none.json")
                bs, edges = extract.extracted_beliefs(use_llm=True, cache_path=empty)
                self.assertEqual(len(bs), 15)   # still produces all beliefs via fallback
                self.assertEqual(edges, [])     # no cache => no LLM edges
        finally:
            extract.llm.available = orig


if __name__ == "__main__":
    unittest.main()
