"""Walk-forward backtest harness — the honest measuring stick.

A *strategy* maps a weekly recommendation (+ only the history available at decision time) to a
planned operative total per working day. The harness enforces the information horizon so no
strategy can ever see an actual it could not have known when deciding (see ANTI_REWARD_HACKING.md).

Information horizon (defensible & strict): a decision is taken on a Tuesday D and plans the FOLLOWING
Mon–Fri. On Tuesday D the current week is still in progress, so the most recent *completed* week is
the one before. We therefore expose actuals only for dates strictly before the **Monday of the
decision week**. The in-progress week is hidden.

Run: python3 eval/backtest.py
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from typing import Callable, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data  # noqa: E402
from src.cost import score_plan, gap_closed_pct, cost_breakdown  # noqa: E402


# --- context exposed to a strategy (history only) -----------------------------------------
class Context:
    """Read-only view of everything knowable at a given decision horizon."""

    def __init__(self, present: Dict[str, float], volumes: Dict[str, Dict[str, float]],
                 rec_op_by_date: Dict[str, float], horizon: str):
        self._present = present
        self._volumes = volumes
        self._rec_op = rec_op_by_date
        self.horizon = horizon  # ISO date; only data strictly before this is visible

    def past_need(self) -> Dict[str, float]:
        """Realized operative need for working days strictly before the horizon."""
        return {d: n for d, n in self._present.items()
                if d < self.horizon and data.is_working_day(d)}

    def past_ratios(self) -> Dict[str, float]:
        """need/recommendation per past working day — the optimiser's realized correction factor."""
        out = {}
        for d, n in self.past_need().items():
            r = self._rec_op.get(d)
            if r:
                out[d] = n / r
        return out

    def past_volumes(self) -> Dict[str, Dict[str, float]]:
        return {d: v for d, v in self._volumes.items() if d < self.horizon}


Strategy = Callable[[data.Recommendation, List[str], Context], Dict[str, float]]


def _decision_week_monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


# --- the harness --------------------------------------------------------------------------
def run(strategy: Strategy, recs=None, present=None, volumes=None, rec_op_by_date=None):
    """Walk forward over every TRAINING cycle (those whose planned week has actuals).

    Returns dict with total strategy/baseline costs, gap-closed %, per-cycle rows, and a breakdown.
    """
    recs = recs or data.load_recommendations()
    present = present if present is not None else data.load_present()
    volumes = volumes if volumes is not None else data.load_volumes()
    if rec_op_by_date is None:
        rec_op_by_date = {}
        for rec in recs.values():
            for d, tot in rec.operative_totals().items():
                if data.is_working_day(d):
                    rec_op_by_date[d] = tot

    full_plan: Dict[str, float] = {}
    full_baseline: Dict[str, float] = {}
    full_need: Dict[str, float] = {}
    rows = []

    for decision_date in sorted(recs):
        rec = recs[decision_date]
        scored_days = [d for d in rec.dates if data.is_working_day(d) and d in present]
        if not scored_days:
            continue  # holdout cycle (no actuals) — skipped in training backtest
        horizon = _decision_week_monday(decision_date)
        ctx = Context(present, volumes, rec_op_by_date, horizon)
        plan = strategy(rec, scored_days, ctx)

        need = {d: present[d] for d in scored_days}
        base = {d: rec.operative_total(d) for d in scored_days}
        s_cost = score_plan(plan, need)
        b_cost = score_plan(base, need)
        rows.append({
            "decision_date": decision_date,
            "days": len(scored_days),
            "strategy_cost": s_cost,
            "baseline_cost": b_cost,
            "gap_closed_pct": gap_closed_pct(s_cost, b_cost),
        })
        full_plan.update(plan)
        full_baseline.update(base)
        full_need.update(need)

    total_s = score_plan(full_plan, full_need)
    total_b = score_plan(full_baseline, full_need)
    return {
        "total_strategy_cost": total_s,
        "total_baseline_cost": total_b,
        "gap_closed_pct": gap_closed_pct(total_s, total_b),
        "n_days": len(full_need),
        "breakdown": cost_breakdown(full_plan, full_need),
        "rows": rows,
    }


# --- baseline ladder (everything we build must beat B2) -----------------------------------
def strat_baseline(rec, days, ctx):
    """B0 — staff exactly the optimiser recommendation (the README 'Baseline' anchor)."""
    return {d: rec.operative_total(d) for d in days}


def make_flat_trim(k: float):
    """B1 — multiply the recommendation by a fixed constant k (e.g. 0.83 == 'trim 17%')."""
    def strat(rec, days, ctx):
        return {d: rec.operative_total(d) * k for d in days}
    strat.__name__ = f"flat_trim_{k}"
    return strat


def make_ew_ratio(halflife_days: float = 14.0, default_k: float = 0.84):
    """B2 — adaptive trim: exponentially-weighted mean of past need/rec ratios, applied to this rec.

    The honest adaptive baseline. Uses ONLY history before the decision horizon.
    """
    decay = 0.5 ** (1.0 / halflife_days)

    def strat(rec, days, ctx):
        ratios = ctx.past_ratios()
        if not ratios:
            k = default_k
        else:
            # weight by recency: most recent date gets weight 1, older decays geometrically
            items = sorted(ratios.items())  # by date
            ref = _dt.date.fromisoformat(items[-1][0])
            num = den = 0.0
            for d, r in items:
                age = (ref - _dt.date.fromisoformat(d)).days
                w = decay ** age
                num += w * r
                den += w
            k = num / den
        return {d: rec.operative_total(d) * k for d in days}
    strat.__name__ = f"ew_ratio_hl{halflife_days}"
    return strat


def _print(name, res):
    print(f"{name:<22} cost €{res['total_strategy_cost']:>10,.0f}   "
          f"gap closed {res['gap_closed_pct']:>5.1f}%   "
          f"(baseline €{res['total_baseline_cost']:,.0f}, {res['n_days']} days)")


if __name__ == "__main__":
    ladder = [
        ("B0 baseline", strat_baseline),
        ("B1 flat -17%", make_flat_trim(0.83)),
        ("B2 EW ratio hl14", make_ew_ratio(14.0)),
        ("B2 EW ratio hl28", make_ew_ratio(28.0)),
    ]
    print("Walk-forward backtest over training cycles (lower cost / higher gap-closed = better)\n")
    for name, strat in ladder:
        _print(name, run(strat))
    print("\nReference (README): baseline ≈ €234.6k, a crude flat trim closes ~86% on holdout.")
