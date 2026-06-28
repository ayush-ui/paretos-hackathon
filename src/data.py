"""Data loaders. Zero-dependency (std-lib csv) — the dataset is tiny and we want full control.

Canonical sources:
  - Recommendations: parsed from the RAW ``recommendations/rec_*.csv`` files so that training AND
    the 4 holdout cycles are covered uniformly (clean/ omits the holdout). German decimals + the
    semicolon/wide format are handled here. See docs/DATA_REFERENCE.md §3-§5.
  - Actuals (target) & volumes: from clean/ (training only; holdout actuals are withheld).

All dates are normalised to ISO ``YYYY-MM-DD`` strings.
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
from collections import defaultdict
from typing import Dict, List, Optional

# --- paths --------------------------------------------------------------------------------
_THIS = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_THIS)
DATA = os.path.join(PROJECT_ROOT, "hackathon-dataset", "data")
CLEAN = os.path.join(DATA, "clean")
RAW_REC = os.path.join(DATA, "recommendations")

ADMIN_CONSTANT = 8.0  # constant admin person-days/day, excluded from scoring

# Public holidays that close the floor (all-zero columns). docs/DATA_REFERENCE.md §4.
FLOOR_CLOSED_HOLIDAYS = frozenset({"2026-05-25", "2026-06-04", "2026-10-03"})

# The 15 operative activities (scored) and 4 admin desks. docs/DATA_REFERENCE.md §5.
OPERATIVE_ACTIVITIES = (
    "Unloading", "Receiving", "Putaway", "Picking", "Staging", "Loading",
    "Replenishment / relocation", "Transit drivers", "Yard shunting", "Team leads",
    "Pick QA", "Co-Packing line", "VNA replenishment", "Returns / QC", "Aisle maintenance",
)
ADMIN_ACTIVITIES = ("Control room", "Outbound office", "Inbound office", "Inventory")

# Raw-file row labels that are section markers / summaries, not activities.
_VOLUME_ROWS = {"PAL_Wareneingang", "VollPAL_Warenausgang", "Picks_Warenausgang", "KomPAL_Warenausgang"}
_SECTION_OPERATIVE = "Mitarbeiter operativ"
_SECTION_ADMIN = "Mitarbeiter administrativ"
_SUMMARY_ROWS = {"Summe operativ", "Summe administrativ"}


# --- small helpers ------------------------------------------------------------------------
def _de_float(s: str) -> Optional[float]:
    """Parse a German-decimal cell ('8,9' -> 8.9). Empty -> None."""
    s = s.strip()
    if not s:
        return None
    return float(s.replace(".", "").replace(",", ".")) if s.count(",") else float(s.replace(",", "."))


def _iso_from_dmy(s: str) -> str:
    """'26.10.2026' -> '2026-10-26'."""
    d, m, y = s.strip().split(".")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def weekday(date_iso: str) -> int:
    """Mon=0 .. Sun=6."""
    return _dt.date.fromisoformat(date_iso).weekday()


def is_working_day(date_iso: str) -> bool:
    return weekday(date_iso) < 5 and date_iso not in FLOOR_CLOSED_HOLIDAYS


# --- recommendations (raw, all 24 cycles) -------------------------------------------------
class Recommendation:
    """One weekly optimiser plan (one rec_*.csv file)."""

    def __init__(self, decision_date: str):
        self.decision_date = decision_date            # the decision Tuesday (filename date)
        self.dates: List[str] = []                    # the 7 planned calendar days (ISO)
        self.volumes: Dict[str, Dict[str, float]] = {}        # date -> {volume_row: value}
        self.by_activity: Dict[str, Dict[str, float]] = {}    # date -> {activity: person_days}
        self.groups: Dict[str, str] = {}              # activity -> 'operative' | 'administrative'

    def operative_total(self, date_iso: str) -> float:
        """Sum of the 15 operative activities for a day (the number we trim)."""
        return sum(v for a, v in self.by_activity.get(date_iso, {}).items()
                   if self.groups.get(a) == "operative")

    def operative_totals(self) -> Dict[str, float]:
        return {d: self.operative_total(d) for d in self.dates}


def parse_raw_rec(path: str) -> Recommendation:
    decision_date = _iso_from_dmy("01." + "01.2000")  # placeholder, overwritten below
    fname = os.path.basename(path)                      # rec_YYYY-MM-DD.csv
    decision_date = fname[len("rec_"):-len(".csv")]
    rec = Recommendation(decision_date)

    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter=";"))

    header = rows[0]
    rec.dates = [_iso_from_dmy(c) for c in header[1:] if c.strip()]
    section = None
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        label = row[0].strip()
        if label == _SECTION_OPERATIVE:
            section = "operative"; continue
        if label == _SECTION_ADMIN:
            section = "administrative"; continue
        if label in _SUMMARY_ROWS:
            continue
        cells = row[1:]
        if label in _VOLUME_ROWS:
            for i, d in enumerate(rec.dates):
                v = _de_float(cells[i]) if i < len(cells) else None
                if v is not None:
                    rec.volumes.setdefault(d, {})[label] = v
            continue
        # otherwise it's an activity row in the current section
        rec.groups[label] = section
        for i, d in enumerate(rec.dates):
            v = _de_float(cells[i]) if i < len(cells) else None
            if v is not None:
                rec.by_activity.setdefault(d, {})[label] = v
    return rec


def load_recommendations() -> Dict[str, Recommendation]:
    """All 24 weekly recommendations keyed by decision date (training + holdout)."""
    out = {}
    for fn in sorted(os.listdir(RAW_REC)):
        if fn.startswith("rec_") and fn.endswith(".csv"):
            rec = parse_raw_rec(os.path.join(RAW_REC, fn))
            out[rec.decision_date] = rec
    return out


# --- actuals (clean; training only) -------------------------------------------------------
def load_present() -> Dict[str, float]:
    """date -> realized operative need N (= present_total - 8). THE prediction target."""
    out = {}
    with open(os.path.join(CLEAN, "present_long.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["date"]] = float(r["present_operative_person_days"])
    return out


def load_volumes() -> Dict[str, Dict[str, float]]:
    """date -> {picks_forecast, picks_realized, outbound_*, inbound_*}."""
    out = {}
    with open(os.path.join(CLEAN, "volumes_long.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            out[r["date"]] = {k: float(v) for k, v in r.items() if k != "date"}
    return out


def load_clean_rec_operative() -> Dict[str, float]:
    """date -> recommended operative total, from clean/ (training only). Cross-check vs raw parser."""
    agg: Dict[str, float] = defaultdict(float)
    with open(os.path.join(CLEAN, "recommendations_long.csv"), newline="") as fh:
        for r in csv.DictReader(fh):
            if r["group"] == "operative":
                agg[r["date"]] += float(r["recommended_person_days"])
    return dict(agg)
