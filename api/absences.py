"""Absence store — the live operational layer on top of the (synthesised) roster.

The hackathon dataset has daily person-day TOTALS only, no named workers, so the roster is a product
layer: 1 person-day = 1 person on 1 shift (target_headcount = round(planned)). An absence on a working
day lowers that day's CONFIRMED headcount by 1; the engine's asymmetric cost model (src/cost.py) then
quantifies the € risk of the resulting shortfall. State is mutable and JSON-persisted so it survives an
API restart during a live demo. This never touches the scored engine numbers — it only models coverage.
"""
from __future__ import annotations

import datetime as _dt
import threading
from typing import Dict, List, Optional

from src.cost import day_cost
from src.persistence import Persistence, get_persistence

_COLLECTION = "absences"
_lock = threading.Lock()


class AbsenceStore:
    def __init__(self, backend: Optional[Persistence] = None):
        self.backend = backend or get_persistence()
        self.absences: List[Dict] = []
        self._next_id = 1
        self._load()

    # --- persistence (behind the swappable adapter; file now, Postgres/Neon later) ---------
    def _load(self) -> None:
        blob = self.backend.load(_COLLECTION)
        if blob:
            self.absences = blob.get("absences", [])
            self._next_id = blob.get("next_id", len(self.absences) + 1)

    def _save(self) -> None:
        self.backend.save(_COLLECTION, {"absences": self.absences, "next_id": self._next_id})

    # --- mutations ------------------------------------------------------------------------
    def add(self, worker: str, date: str, reason: str, source: str = "app") -> Dict:
        with _lock:
            rec = {
                "id": self._next_id,
                "worker": worker,
                "date": date,
                "reason": reason or "",
                "source": source,
                "status": "open",  # open | resolved
                "resolution": None,
                "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
            }
            self.absences.append(rec)
            self._next_id += 1
            self._save()
            return rec

    def resolve(self, absence_id: int, option: str) -> Optional[Dict]:
        with _lock:
            for rec in self.absences:
                if rec["id"] == absence_id:
                    rec["status"] = "resolved"
                    rec["resolution"] = option  # "filled" | "accepted"
                    self._save()
                    return rec
            return None

    def clear(self) -> None:
        """Reset all absences (demo convenience)."""
        with _lock:
            self.absences = []
            self._next_id = 1
            self._save()

    # --- reads ----------------------------------------------------------------------------
    def list(self) -> List[Dict]:
        return list(self.absences)

    def open_count_by_date(self) -> Dict[str, int]:
        """Number of OPEN absences per date (a 'filled' resolution restores coverage; 'accepted' keeps
        the gap counted as still short)."""
        out: Dict[str, int] = {}
        for r in self.absences:
            if r["status"] == "open" or r.get("resolution") == "accepted":
                out[r["date"]] = out.get(r["date"], 0) + 1
        return out


def coverage_for_day(target: int, absences_today: int) -> Dict:
    """Coverage + € risk for one day given the target headcount and # of effective absences.
    Risk uses the real asymmetric cost model: shortfall premium + SLA penalty beyond 2.0."""
    confirmed = max(0, target - absences_today)
    short_by = max(0, target - confirmed)
    # marginal € cost of staffing `confirmed` when `target` were needed (day_cost(target,target)=0)
    sla_risk = round(day_cost(confirmed, target)) if short_by else 0
    return {
        "confirmed_headcount": confirmed,
        "coverage": "short" if short_by else "covered",
        "short_by": short_by,
        "sla_risk_eur": sla_risk,
    }


_STORE: Optional[AbsenceStore] = None


def get_store() -> AbsenceStore:
    global _STORE
    if _STORE is None:
        _STORE = AbsenceStore()
    return _STORE
