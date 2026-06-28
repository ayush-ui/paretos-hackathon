"""LLM-integration tests.

These run WITHOUT an API key (the CI/default state), so they verify the all-important property:
with no LLM, the system degrades gracefully and the NUMBERS ARE UNCHANGED. (Live-LLM behavior is
not unit-tested here — it would require a billed key and is non-deterministic.)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import llm, note_parser, narrator, data, curate, predict  # noqa: E402
from eval.backtest import run  # noqa: E402


def _force_no_key():
    """Simulate the no-key state regardless of any .env / env var present in this run."""
    os.environ["ANTHROPIC_API_KEY"] = ""   # falsy → llm treats it as absent
    llm._client = None
    llm._checked = False


class TestLlmUnavailableFallback(unittest.TestCase):
    def setUp(self):
        _force_no_key()

    def test_not_available_without_key(self):
        self.assertFalse(llm.available())

    def test_narrate_returns_none(self):
        self.assertIsNone(llm.narrate("anything"))

    def test_parse_note_returns_none(self):
        self.assertIsNone(note_parser.parse_note("drivers tired due to heat wave"))

    def test_narrator_explain_returns_none(self):
        trace = {"date": "2026-09-07", "recommended": 65.3, "planned": 53.9, "k": 0.823,
                 "regime_boundary": "2026-08-25", "trend_adj": 0.5}
        self.assertIsNone(narrator.explain_plan(trace))


class TestNumbersUnaffectedByLlm(unittest.TestCase):
    """The headline guarantee: the engine's cost is computed with zero LLM involvement."""

    def test_engine_cost_is_deterministic(self):
        # The engine code path never calls the LLM, so the cost is identical whether or not a key is
        # configured — this is the headline 'LLM never touches the numbers' guarantee.
        g = curate.build_graph()
        curate.curate(g, data.load_present(), data.load_recommendations())
        cost = run(predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4).as_strategy())
        self.assertEqual(round(cost["total_strategy_cost"]), 16346)  # same as pre-LLM build


class TestParsedNoteSchema(unittest.TestCase):
    """The structured schema a live LLM would fill — validated here without calling out."""

    def test_one_off_becomes_zero_trust_candidate(self):
        from src.note_parser import ParsedNote, to_candidate_belief
        parsed = ParsedNote(kind="note", activities=[], is_one_off=True, confidence=0.1,
                            rationale="single absence, not a pattern")
        b = to_candidate_belief(parsed, "N99", "2026-07-01", author="Test", note_text="Max absent")
        self.assertEqual(b.status, "candidate")
        self.assertEqual(b.trust, 0.0)  # a one-off never starts trusted

    def test_pattern_becomes_low_trust_candidate(self):
        from src.note_parser import ParsedNote, to_candidate_belief
        parsed = ParsedNote(kind="scale_pct", activities=["Picking"], pct=-20.0,
                            is_one_off=False, confidence=0.8, rationale="recurring heat effect")
        b = to_candidate_belief(parsed, "N98", "2026-08-01")
        self.assertEqual(b.status, "candidate")  # still a candidate — must pass curation
        self.assertGreater(b.trust, 0.0)
        self.assertLessEqual(b.trust, 0.5)       # never auto-trusted above the candidate ceiling


if __name__ == "__main__":
    unittest.main()
