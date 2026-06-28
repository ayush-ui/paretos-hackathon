"""Data-integrity tests: the raw recommendation parser must agree with the clean export, and
loaders must expose sane, leak-free structures.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data  # noqa: E402


class TestRawVsClean(unittest.TestCase):
    """The raw parser is our canonical recommendation source; verify it matches clean/ on training."""

    @classmethod
    def setUpClass(cls):
        cls.recs = data.load_recommendations()
        cls.clean_op = data.load_clean_rec_operative()

    def test_all_24_cycles_present(self):
        self.assertEqual(len(self.recs), 24)

    def test_raw_operative_totals_match_clean(self):
        # For every date the clean file covers, the raw parser must reproduce the operative total.
        raw_op = {}
        for rec in self.recs.values():
            for d, tot in rec.operative_totals().items():
                raw_op[d] = tot
        checked = 0
        for d, clean_tot in self.clean_op.items():
            self.assertIn(d, raw_op, f"date {d} missing from raw parse")
            self.assertAlmostEqual(raw_op[d], clean_tot, places=4,
                                   msg=f"raw vs clean mismatch on {d}")
            checked += 1
        self.assertGreater(checked, 90)  # ~98 training days

    def test_15_operative_activities(self):
        rec = next(iter(self.recs.values()))
        ops = [a for a, g in rec.groups.items() if g == "operative"]
        self.assertEqual(set(ops), set(data.OPERATIVE_ACTIVITIES))


class TestActuals(unittest.TestCase):
    def test_present_is_training_only(self):
        present = data.load_present()
        # Holdout actuals must NOT be present (anti-leakage). Holdout planned weeks are in October.
        self.assertTrue(max(present) <= "2026-10-02",
                        "present_long should not contain holdout-week actuals")

    def test_german_decimal_parsing(self):
        self.assertAlmostEqual(data._de_float("8,9"), 8.9)
        self.assertIsNone(data._de_float("  "))
        self.assertAlmostEqual(data._de_float("4"), 4.0)

    def test_working_day_excludes_weekend_and_holiday(self):
        self.assertTrue(data.is_working_day("2026-05-18"))   # Monday
        self.assertFalse(data.is_working_day("2026-05-23"))  # Saturday
        self.assertFalse(data.is_working_day("2026-05-25"))  # Whit Monday holiday


if __name__ == "__main__":
    unittest.main()
