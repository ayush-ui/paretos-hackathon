"""The belief graph — the knowledge / curation layer (Phase 3).

A *belief* is a structured, time-scoped claim about how the optimiser's recommendation diverges
from reality (e.g. "Co-Packing is a fixed crew of 4", "picking runs -25% after pick-by-light").
Beliefs come from two sources:
  - the decision log (planner notes L01-L15, ingested as CANDIDATES — claims, not facts), and
  - data-derived change-point detection (regime shifts the engine finds itself).

Beliefs are connected by typed edges (supersedes / contradicts / reaffirms / refines) and carry a
validity window + trust + status. Curation (trust update, supersession, contradiction resolution,
expiry) is DATA-DRIVEN and lives in `curate.py` — nothing here hardcodes a verdict.

IMPORTANT (anti-reward-hacking): ingestion respects `captured_on` as `valid_from`; a belief can
only influence a decision made on/after the date its evidence existed. See ANTI_REWARD_HACKING.md.

Because actuals are TOTAL-only (docs/DATA_REFERENCE §6b), a belief's effect is realised by adjusting
the optimiser's *activity-level* recommendation and re-summing the operative total; its trust is then
measured by whether that adjustment improves walk-forward cost.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import data

# Map the decision-log's loose activity keys to canonical activity names (DATA_REFERENCE §5).
ACTIVITY_KEY = {
    "transit": "Transit drivers",
    "co_packing": "Co-Packing line",
    "picking": "Picking",
    "receiving": "Receiving",
    "loading": "Loading",
    "putaway": "Putaway",
    "vna_replen": "VNA replenishment",
    "staging": "Staging",
}
# Volume rows in the rec file, available at decision time (FORECAST, no leakage).
_PICKS_FC = "Picks_Warenausgang"
_INBOUND_FC = "PAL_Wareneingang"

Status = str  # 'candidate' | 'active' | 'stale' | 'retired'


@dataclass
class Belief:
    id: str
    source: str                       # 'log' | 'derived'
    kind: str                         # fixed | scale_pct | add | conditional_trim | conditional_add | trend | note
    activities: List[str]             # canonical activity names this belief touches ([] for operative-wide/note)
    params: Dict = field(default_factory=dict)
    valid_from: str = "2026-01-01"    # ISO; first decision date this may inform
    valid_to: Optional[str] = None    # ISO exclusive; None == open
    weekday: Optional[str] = None     # 'Mon' | 'payday-Mon' | None
    condition: Optional[str] = None   # e.g. 'picks < 7000' | 'inbound > 2000' | 'day-after-closure'
    scope_weeks: Optional[List[str]] = None  # ISO date bounds [start, end] for time-boxed beliefs
    trust: float = 0.5                # [0,1]; updated by curation
    status: Status = "candidate"
    author: Optional[str] = None
    note: str = ""
    evidence: List[str] = field(default_factory=list)

    def active_on(self, date_iso: str, decision_date: str) -> bool:
        """Is this belief eligible to fire for a planned `date`, decided on `decision_date`?"""
        if self.status in ("retired",):
            return False
        if decision_date < self.valid_from:          # not yet known
            return False
        if self.valid_to is not None and date_iso >= self.valid_to:
            return False
        if self.scope_weeks and not (self.scope_weeks[0] <= date_iso <= self.scope_weeks[1]):
            return False
        return True

    def to_dict(self) -> Dict:
        d = self.__dict__.copy()
        return d


# --- conditions / weekday gating ----------------------------------------------------------
def _is_payday_monday(date_iso: str) -> bool:
    """Last Monday of the month."""
    d = _dt.date.fromisoformat(date_iso)
    if d.weekday() != 0:
        return False
    return (d + _dt.timedelta(days=7)).month != d.month  # no Monday next week in same month


def _day_after_closure(date_iso: str) -> bool:
    """First working day following a closed day (weekend or floor-closing holiday)."""
    prev = (_dt.date.fromisoformat(date_iso) - _dt.timedelta(days=1)).isoformat()
    # walk back over consecutive closed days; if the immediately preceding calendar day was closed
    # AND this day is a working day, it's a day-after-closure.
    if not data.is_working_day(date_iso):
        return False
    return (not data.is_working_day(prev))


def _weekday_ok(belief: Belief, date_iso: str) -> bool:
    if belief.weekday is None:
        return True
    if belief.weekday == "Mon":
        return data.weekday(date_iso) == 0
    if belief.weekday == "payday-Mon":
        return _is_payday_monday(date_iso)
    return True


def _condition_ok(belief: Belief, date_iso: str, rec: "data.Recommendation") -> bool:
    if belief.condition is None:
        return True
    vol = rec.volumes.get(date_iso, {})
    if belief.condition == "day-after-closure":
        return _day_after_closure(date_iso)
    if belief.condition.startswith("picks <"):
        thr = float(belief.condition.split("<")[1])
        return vol.get(_PICKS_FC, float("inf")) < thr
    if belief.condition.startswith("inbound >"):
        thr = float(belief.condition.split(">")[1])
        return vol.get(_INBOUND_FC, 0.0) > thr
    return True


# --- applying beliefs to a recommendation -------------------------------------------------
def apply_beliefs(rec: "data.Recommendation", date_iso: str, beliefs: List[Belief],
                  decision_date: str, active_only: bool = True) -> Dict[str, float]:
    """Return an adjusted activity->person_days map for `date_iso` after firing eligible beliefs.

    Pure structural adjustment of the optimiser's plan; does NOT apply the global residual trim
    (that is the predictor's job). Beliefs of kind 'note'/'trend' are ignored here (handled by the
    trend component of the predictor).
    """
    adj = dict(rec.by_activity.get(date_iso, {}))
    for b in beliefs:
        if active_only and b.status not in ("active", "candidate"):
            continue
        if not b.active_on(date_iso, decision_date):
            continue
        if not _weekday_ok(b, date_iso) or not _condition_ok(b, date_iso, rec):
            continue
        if b.kind == "fixed":
            for a in b.activities:
                if a in adj:
                    adj[a] = float(b.params["value"])
        elif b.kind == "scale_pct":
            f = 1.0 + float(b.params["pct"]) / 100.0
            if b.activities:
                for a in b.activities:
                    if a in adj:
                        adj[a] *= f
            else:  # operative-wide scaling (e.g. L08)
                for a in list(adj):
                    if rec.groups.get(a) == "operative":
                        adj[a] *= f
        elif b.kind in ("add", "conditional_add"):
            for a in b.activities:
                if a in adj:
                    adj[a] += float(b.params.get("delta", 0))
        elif b.kind == "conditional_trim":
            for a in b.activities:
                if a in adj:
                    adj[a] += float(b.params.get("delta", 0))  # delta is negative
        # 'note' / 'trend' -> no structural change here
    return adj


def adjusted_operative_total(rec, date_iso, beliefs, decision_date, active_only=True) -> float:
    adj = apply_beliefs(rec, date_iso, beliefs, decision_date, active_only)
    return sum(v for a, v in adj.items() if rec.groups.get(a) == "operative")


# --- graph container ----------------------------------------------------------------------
@dataclass
class Edge:
    src: str
    dst: str
    kind: str  # supersedes | contradicts | reaffirms | refines


class BeliefGraph:
    def __init__(self):
        self.beliefs: Dict[str, Belief] = {}
        self.edges: List[Edge] = []

    def add(self, b: Belief):
        self.beliefs[b.id] = b

    def add_edge(self, src: str, dst: str, kind: str):
        self.edges.append(Edge(src, dst, kind))

    def active(self) -> List[Belief]:
        return [b for b in self.beliefs.values() if b.status in ("active", "candidate")]

    def list(self) -> List[Belief]:
        return list(self.beliefs.values())

    def to_json(self) -> str:
        return json.dumps({
            "beliefs": [b.to_dict() for b in self.beliefs.values()],
            "edges": [e.__dict__ for e in self.edges],
        }, indent=2)

    def save(self, path: str):
        with open(path, "w") as fh:
            fh.write(self.to_json())

    def render_text(self, as_of: Optional[str] = None) -> str:
        """A human-readable view of the curated graph: nodes grouped by status + typed edges.

        With ``as_of`` set, beliefs not yet captured by then are hidden — an honest snapshot of what
        the planner knew at that date. Same node/edge content a Neo4j export (Phase 6) would carry.
        """
        order = {"active": 0, "candidate": 1, "stale": 2, "retired": 3}
        known = [b for b in self.beliefs.values() if as_of is None or b.valid_from < as_of]
        known_ids = {b.id for b in known}
        lines = ["BELIEF GRAPH  (status | id | kind | scope | window | trust)"]
        for b in sorted(known, key=lambda x: (order.get(x.status, 9), x.id)):
            scope = ", ".join(b.activities) or (b.note[:30] if b.note else "operative")
            window = b.valid_from + (" .. " + b.valid_to if b.valid_to else " .. (open)")
            mark = {"active": "[A]", "candidate": "[.]", "stale": "[s]", "retired": "[x]"}.get(b.status, "[?]")
            lines.append("  %s %-4s %-16s %-22s %-26s t=%.2f" % (
                mark, b.id, b.kind, scope[:22], window, b.trust))
        visible_edges = [e for e in self.edges if e.src in known_ids and e.dst in known_ids]
        if visible_edges:
            lines.append("\nEDGES (knowledge relationships):")
            sym = {"supersedes": "──supersedes──▶", "contradicts": "◀─contradicts─▶",
                   "reaffirms": "──reaffirms──▶", "refines": "──refines──▶"}
            for e in visible_edges:
                lines.append("  %-4s %s %-4s" % (e.src, sym.get(e.kind, e.kind), e.dst))
        return "\n".join(lines)


# --- ingestion from the decision log ------------------------------------------------------
def _acts(claim, scope) -> List[str]:
    keys = []
    if "activities" in claim:
        keys = claim["activities"]
    elif "activity" in claim:
        keys = [claim["activity"]]
    elif isinstance(scope, list):
        keys = scope
    elif isinstance(scope, str) and scope in ACTIVITY_KEY:
        keys = [scope]
    return [ACTIVITY_KEY[k] for k in keys if k in ACTIVITY_KEY]


# Map W-numbers used in the log to ISO date ranges (Mon-Fri). W30-W33 ~ late Jul-mid Aug 2026.
_WEEK_RANGES = {
    "W30–W33": ["2026-07-20", "2026-08-16"],
}


def belief_from_entry(e: Dict, claim: Optional[Dict] = None, evidence_tag: str = "decision_log") -> Belief:
    """Build a Belief from one decision-log entry. `claim` overrides e['claimed_effect'] (this is the
    seam the LLM-first extractor uses: it supplies a richer claim parsed from the prose; with no claim
    we fall back to the structured `claimed_effect` hint already in the dataset). One builder, two
    sources — so the deterministic hint path and the LLM path produce identically-shaped beliefs.
    """
    claim = claim if claim is not None else e.get("claimed_effect", {})
    kind = claim.get("kind", "note")
    acts = _acts(claim, e.get("scope"))
    b = Belief(
        id=e["id"], source="log", kind=kind, activities=acts,
        valid_from=e["captured_on"], author=e.get("author"), note=e["note"],
        evidence=[f"{evidence_tag}:{e['id']}"],
    )
    if kind == "fixed":
        b.params = {"value": claim["value"]}
    elif kind == "scale_pct":
        b.params = {"pct": claim["pct"]}
        if "from" in claim and claim["from"]:
            b.valid_from = max(b.valid_from, claim["from"])
        if claim.get("weeks") in _WEEK_RANGES:
            b.scope_weeks = _WEEK_RANGES[claim["weeks"]]
    elif kind in ("add",):
        b.params = {"delta": claim["delta"]}
        b.weekday = claim.get("weekday")
        if claim.get("when") == "day-after-closure":
            b.condition = "day-after-closure"
    elif kind == "conditional_trim":
        b.params = {"delta": claim["delta"]}
        b.condition = claim.get("when")
    elif kind == "conditional_add":
        b.params = {"delta": claim["delta"]}
        b.condition = claim.get("when")
    elif kind == "note":
        b.params = {k: v for k, v in claim.items() if k != "kind"}
    return b


def load_log(path: Optional[str] = None) -> Dict:
    path = path or os.path.join(data.DATA, "decision_log.json")
    with open(path) as fh:
        return json.load(fh)


def ingest_decision_log(path: Optional[str] = None) -> List[Belief]:
    """Deterministic ingestion from the `claimed_effect` hints — the always-available fallback path."""
    return [belief_from_entry(e) for e in load_log(path)["entries"]]


def derive_edges(beliefs: List[Belief]) -> List[Edge]:
    """Structural edges inferable from the claims themselves (NOT verdicts — those come from data).

    - A later belief with a `valid_from` on the same activity SUPERSEDES an earlier open-ended one
      (the new evidence opens a new regime; the engine will close the old one's window in curation).
    - Two beliefs on the same activity with the same kind/value REAFFIRM each other.
    - An operative-wide cut and an operative-wide 'don't cut' note in overlapping time CONTRADICT.
    """
    edges = []
    by_act: Dict[str, List[Belief]] = {}
    for b in beliefs:
        for a in (b.activities or ["__operative__"]):
            by_act.setdefault(a, []).append(b)
    for a, bs in by_act.items():
        bs = sorted(bs, key=lambda x: x.valid_from)
        for i, b in enumerate(bs):
            for earlier in bs[:i]:
                if b.kind == "fixed" and earlier.kind == "fixed" and \
                        b.params.get("value") == earlier.params.get("value"):
                    edges.append(Edge(b.id, earlier.id, "reaffirms"))
                elif b.kind == "scale_pct" and earlier.kind == "scale_pct" and \
                        b.valid_from > earlier.valid_from and "from" not in earlier.__dict__:
                    edges.append(Edge(b.id, earlier.id, "supersedes"))
    # Contradiction: an operative-wide cut and an operative-wide note disputing it, captured close
    # in time (e.g. L08 'cut 15%' vs L09 'do not cut'). The data, not us, decides which survives.
    op = sorted(by_act.get("__operative__", []), key=lambda x: x.valid_from)
    for i, b in enumerate(op):
        for other in op[:i]:
            cut = b if b.kind == "scale_pct" else (other if other.kind == "scale_pct" else None)
            note = b if b.kind == "note" else (other if other.kind == "note" else None)
            if cut is not None and note is not None and cut is not note:
                d1 = _dt.date.fromisoformat(b.valid_from)
                d2 = _dt.date.fromisoformat(other.valid_from)
                if abs((d1 - d2).days) <= 14:
                    edges.append(Edge(note.id, cut.id, "contradicts"))
    return edges
