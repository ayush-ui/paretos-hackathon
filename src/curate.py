"""Curation — the data-driven governance that makes the loop *compound* (Phase 3).

Given the candidate beliefs ingested from the decision log, curation decides — from ACTUALS, never
from hardcoded verdicts — what to trust, when, and for how long:

  1. ENFORCE SUPERSESSION: when a newer belief covers the same activity as an older open-ended one,
     close the old one's validity window at the new one's start. This is how stale knowledge expires
     (e.g. the pick-by-light note closes the old -12% picking trim on 2026-08-24) and how we avoid
     DOUBLE-APPLYING overlapping scale beliefs.
  2. SCORE TRUST by walk-forward marginal contribution: include a belief only over the history a
     planner could have seen; measure €cost(with) - €cost(without) on its in-scope days. Beliefs
     that pay off gain trust and go ACTIVE; beliefs that hurt (e.g. the L08 'cut 15%' trap) are
     RETIRED with a recorded reason. Contradictions resolve automatically: the member that improves
     cost survives.

Everything here is measured on TRAINING actuals strictly before the relevant decision — no holdout
peeking (ANTI_REWARD_HACKING.md).
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional, Tuple

from . import data, beliefs
from .beliefs import Belief, BeliefGraph, Edge
from .cost import score_plan

# A belief whose inclusion raises walk-forward cost by more than this (EUR, over its scope) is
# retired. Small positive noise is tolerated so we don't churn on irreducible day-to-day variance.
RETIRE_HURT_THRESHOLD = 50.0
PROMOTE_HELP_THRESHOLD = 50.0


def _monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def build_graph(log_path: Optional[str] = None, use_llm: bool = False,
                cache_path: Optional[str] = None) -> BeliefGraph:
    """Build the belief graph from the decision log.

    use_llm=False (default): deterministic hint/cache ingestion — reproduces the locked numbers and
    needs no API key. use_llm=True: LLM-first extraction (fills + uses the reviewed cache) plus the
    LLM-flagged contradicts/supersedes edges, unioned with the structural detector for completeness.
    """
    from . import extract
    g = BeliefGraph()
    bs, llm_edges = extract.extracted_beliefs(log_path, use_llm=use_llm, cache_path=cache_path)
    for b in bs:
        g.add(b)
    seen = set()
    for e in list(llm_edges) + beliefs.derive_edges(bs):
        key = (e.src, e.dst, e.kind)
        if key in seen or e.src not in g.beliefs or e.dst not in g.beliefs:
            continue
        seen.add(key)
        g.add_edge(e.src, e.dst, e.kind)
    return g


def enforce_supersession(g: BeliefGraph, as_of: Optional[str] = None) -> None:
    """Close the validity window of any belief that a newer same-scope belief supersedes.

    With ``as_of`` set, only superseding beliefs already captured by then take effect — a planner
    cannot retire a belief using a note that has not been written yet.
    """
    for e in g.edges:
        if e.kind != "supersedes":
            continue
        newer, older = g.beliefs[e.src], g.beliefs[e.dst]
        if as_of is not None and newer.valid_from >= as_of:
            continue
        cut = newer.valid_from
        if older.valid_to is None or cut < older.valid_to:
            older.valid_to = cut
            older.evidence.append(f"window closed at {cut} by {newer.id} (supersession)")


# --- structural-adjustment plan builder used for scoring beliefs --------------------------
def _plan_cost_over(active: List[Belief], present: Dict[str, float], recs, k: float,
                    restrict_dates=None) -> Tuple[float, int]:
    """Total cost of (structural beliefs -> operative total -> *k) vs actuals, over scored days."""
    plan, need = {}, {}
    for dd in sorted(recs):
        rec = recs[dd]
        for d in rec.dates:
            if not (data.is_working_day(d) and d in present):
                continue
            if restrict_dates is not None and d not in restrict_dates:
                continue
            plan[d] = beliefs.adjusted_operative_total(rec, d, active, dd, active_only=False) * k
            need[d] = present[d]
    if not need:
        return 0.0, 0
    return score_plan(plan, need), len(need)


def _best_k(active: List[Belief], present, recs, restrict_dates=None) -> Tuple[float, float]:
    """In-sample best residual trim for a belief set (used only to compare belief sets fairly)."""
    best_c, best_k = float("inf"), 1.0
    for i in range(72, 101):
        k = i / 100.0
        c, _ = _plan_cost_over(active, present, recs, k, restrict_dates)
        if c < best_c:
            best_c, best_k = c, k
    return best_c, best_k


def _scope_dates(b: Belief, present, recs) -> List[str]:
    """Scored dates on which belief b actually fires (window + weekday + condition all satisfied)."""
    out = []
    for dd in sorted(recs):
        rec = recs[dd]
        for d in rec.dates:
            if not (data.is_working_day(d) and d in present):
                continue
            if not b.active_on(d, dd):
                continue
            if not beliefs._weekday_ok(b, d) or not beliefs._condition_ok(b, d, rec):
                continue
            out.append(d)
    return out


def curate(g: BeliefGraph, present: Optional[Dict[str, float]] = None, recs=None,
           verbose: bool = False, as_of: Optional[str] = None) -> BeliefGraph:
    """Run the full curation pass. Mutates and returns g.

    Strategy: enforce supersession, then forward-prune — repeatedly retire the single belief whose
    removal most reduces cost, until no remaining belief is net-harmful. Survivors that help on
    their own scope are promoted to ACTIVE; pure 'note' beliefs are parked (the trend component
    consumes them, not the structural adjuster).

    ``as_of`` (ISO date) makes curation honest/walk-forward: only actuals STRICTLY BEFORE this date
    are used to judge beliefs. A belief not yet captured by ``as_of`` is left untouched (candidate) —
    it cannot be validated against evidence that does not exist yet. This is what lets the live loop
    (eval/compounding.py) show a belief like L08 being retired only AFTER enough weeks accrue.
    """
    present = present if present is not None else data.load_present()
    recs = recs or data.load_recommendations()
    if as_of is not None:
        present = {d: v for d, v in present.items() if d < as_of}
    enforce_supersession(g, as_of=as_of)

    # A belief can only be judged once it has been captured AND has some evidence window behind it.
    def _known(b):
        return as_of is None or b.valid_from < as_of

    structural = [b for b in g.list() if b.kind not in ("note", "trend") and _known(b)]
    notes = [b for b in g.list() if b.kind in ("note", "trend") and _known(b)]
    for b in notes:
        b.status = "active" if b.params.get("trend") else "candidate"
        b.evidence.append("non-numeric note: consumed by trend component, not structural adjuster")

    # Forward pruning on the full structural set.
    survivors = list(structural)
    while True:
        base_c, base_k = _best_k(survivors, present, recs)
        worst_id, worst_gain = None, 0.0
        for b in survivors:
            rest = [x for x in survivors if x.id != b.id]
            c_without, _ = _best_k(rest, present, recs)
            gain = base_c - c_without  # >0 means removing b lowers cost => b hurts
            if gain > worst_gain:
                worst_gain, worst_id = gain, b.id
        if worst_id is None or worst_gain <= RETIRE_HURT_THRESHOLD:
            break
        bad = g.beliefs[worst_id]
        bad.status = "retired"
        bad.trust = 0.0
        bad.evidence.append(f"retired: removing it cut walk-forward cost by EUR {worst_gain:.0f}")
        survivors = [x for x in survivors if x.id != worst_id]
        if verbose:
            print(f"  RETIRE {worst_id} ({bad.kind} {bad.activities or bad.note[:30]}): "
                  f"saves EUR {worst_gain:.0f}")

    # Promote survivors that demonstrably help on their own scope; assign trust from € saved.
    final_c, _ = _best_k(survivors, present, recs)
    for b in survivors:
        scope = _scope_dates(b, present, recs)
        if not scope:
            b.status = "candidate"
            b.evidence.append("no in-scope scored days in training; left as candidate")
            continue
        rest = [x for x in survivors if x.id != b.id]
        c_with, _ = _best_k(survivors, present, recs, restrict_dates=set(scope))
        c_without, _ = _best_k(rest, present, recs, restrict_dates=set(scope))
        help_eur = c_without - c_with  # >0 means belief helps on its scope
        if help_eur >= PROMOTE_HELP_THRESHOLD:
            b.status = "active"
            b.trust = min(1.0, 0.5 + help_eur / 5000.0)
            b.evidence.append(f"promoted ACTIVE: saves EUR {help_eur:.0f} on its {len(scope)} scope-days")
        else:
            b.status = "active" if b.status == "active" else "candidate"
            b.trust = 0.5
            b.evidence.append(f"weak/neutral on scope (EUR {help_eur:+.0f}); kept as {b.status}")
    return g


def active_structural(g: BeliefGraph) -> List[Belief]:
    return [b for b in g.list() if b.status == "active" and b.kind not in ("note",)]
