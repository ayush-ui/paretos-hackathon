"""The live compounding loop — the headline 'gets smarter every week' demonstration (Phase 5).

Unlike eval/submit.py (which curates once on all training data), this re-curates the belief graph
*as of* each decision week, using ONLY actuals known by then, and plans that week with the resulting
engine. It then prints:
  - the BELIEF LIFECYCLE: when each belief flips candidate -> active / retired / superseded as
    evidence accrues (e.g. L08 retired only after the late-summer weeks are observed; L03 superseded
    at pick-by-light), and
  - the running cost vs the do-nothing baseline, proving the loop compounds rather than memorises.

Fully walk-forward; no holdout actuals are touched (ANTI_REWARD_HACKING.md).

Run: python3 eval/compounding.py
"""
from __future__ import annotations

import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from src.cost import score_plan, gap_closed_pct  # noqa: E402
from eval.backtest import Context  # noqa: E402

# Glyph per status for the lifecycle grid.
_GLYPH = {"active": "A", "candidate": ".", "retired": "x", "stale": "s"}
# Beliefs whose lifecycle is the interesting story to display.
_WATCH = ["L01", "L02", "L03", "L08", "L09", "L11", "L12"]


def _monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def run_live(halflife: float = 21.0, offset: float = 0.3, trend_gain: float = 0.4, verbose=True):
    present = data.load_present()
    recs = data.load_recommendations()
    volumes = data.load_volumes()
    rec_op_by_date = {d: t for r in recs.values()
                      for d, t in r.operative_totals().items() if data.is_working_day(d)}

    plan_all, base_all, need_all = {}, {}, {}
    timeline = []  # (decision_date, {belief_id: status}, cycle_cost, cycle_base)

    for dd in sorted(recs):
        rec = recs[dd]
        scored = [d for d in rec.dates if data.is_working_day(d) and d in present]
        if not scored:
            continue  # holdout cycle (no actuals) — not part of the training compounding curve
        as_of = _monday(dd)

        # Re-curate from scratch using ONLY data known by this week (the honest, live view).
        g = curate.build_graph()
        curate.curate(g, present, recs, as_of=as_of)
        engine = predict.Engine(g, halflife=halflife, offset=offset, trend_gain=trend_gain)

        ctx = Context(present, volumes, rec_op_by_date, as_of)
        plan = engine.plan_cycle(rec, scored, ctx)

        need = {d: present[d] for d in scored}
        base = {d: rec.operative_total(d) for d in scored}
        plan_all.update(plan); base_all.update(base); need_all.update(need)
        timeline.append((dd, {b: g.beliefs[b].status for b in _WATCH},
                         score_plan(plan, need), score_plan(base, need)))

    if verbose:
        _print_report(timeline, plan_all, base_all, need_all)
    return timeline, score_plan(plan_all, need_all), score_plan(base_all, need_all)


def _print_report(timeline, plan_all, base_all, need_all):
    print("LIVE COMPOUNDING LOOP — belief lifecycle + running cost (walk-forward, no peeking)\n")
    print("Belief status per week  (A=active  .=candidate/unknown  x=retired)")
    print("  decision     " + "  ".join("%4s" % b for b in _WATCH) + "   cum.gap%")
    cum_p, cum_b = 0.0, 0.0
    for dd, statuses, cyc_cost, cyc_base in timeline:
        cum_p += cyc_cost; cum_b += cyc_base
        grid = "  ".join("%4s" % _GLYPH.get(statuses[b], "?") for b in _WATCH)
        print("  %-11s  %s   %6.1f" % (dd, grid, gap_closed_pct(cum_p, cum_b)))

    tot_p = score_plan(plan_all, need_all)
    tot_b = score_plan(base_all, need_all)
    print("\nFINAL  engine EUR %.0f vs baseline EUR %.0f  ->  gap closed %.2f%%  (%d days)" % (
        tot_p, tot_b, gap_closed_pct(tot_p, tot_b), len(need_all)))
    print("\nLifecycle highlights to look for:")
    print("  - L08 ('cut 15%%'): flips . -> x once the late-summer weeks are observed (the trap dies).")
    print("  - L03 (old picking -12%%): superseded/retired around pick-by-light; L11 takes over.")
    print("  This status CHANGING over time is the 'compounds, and retires stale beliefs' story.")


if __name__ == "__main__":
    run_live()
