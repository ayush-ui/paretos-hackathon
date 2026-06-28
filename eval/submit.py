"""Generate the holdout submission and the compounding report.

Submission format (README §5): `date,planned_operative_person_days` for the 4 October holdout weeks.
The engine is fit on TRAINING only and applied walk-forward to the holdout (which lies entirely
after training) — no holdout actuals are ever read. See ANTI_REWARD_HACKING.md.

Run: python3 eval/submit.py
"""
from __future__ import annotations

import csv
import datetime as _dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from eval.backtest import Context, run, make_ew_ratio, make_flat_trim, strat_baseline  # noqa: E402

OUT_DIR = os.path.join(data.PROJECT_ROOT, "submissions")
HOLDOUT_DECISIONS = ("2026-09-29", "2026-10-06", "2026-10-13", "2026-10-20")


def _monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def build_engine():
    present = data.load_present()
    recs = data.load_recommendations()
    g = curate.build_graph()
    curate.curate(g, present, recs)
    engine = predict.Engine(g, halflife=21.0, offset=0.3, trend_gain=0.4)
    return engine, g, present, recs


def generate_submission():
    engine, g, present, recs = build_engine()
    volumes = data.load_volumes()
    # rec operative by date for the whole dataset (history ratios come from training only via present)
    rec_op_by_date = {d: t for r in recs.values()
                      for d, t in r.operative_totals().items() if data.is_working_day(d)}

    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for dd in HOLDOUT_DECISIONS:
        rec = recs[dd]
        horizon = _monday(dd)
        ctx = Context(present, volumes, rec_op_by_date, horizon)
        scored_days = [d for d in rec.dates if data.is_working_day(d)]
        plan = engine.plan_cycle(rec, scored_days, ctx)
        for d in sorted(plan):
            rows.append((d, round(plan[d], 2)))

    path = os.path.join(OUT_DIR, "submission.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "planned_operative_person_days"])
        w.writerows(rows)
    return path, rows


def compounding_report():
    """Per-cycle walk-forward gap-closed for the headline engine vs the bar (B2)."""
    engine, g, present, recs = build_engine()
    res = run(engine.as_strategy())
    b2 = run(make_ew_ratio(14))
    print("Per-cycle walk-forward (engine vs cumulative):")
    print("  decision     days   engine€    gapclosed%")
    for r in res["rows"]:
        print("  %-11s  %4d  %9.0f   %6.1f" % (
            r["decision_date"], r["days"], r["strategy_cost"], r["gap_closed_pct"]))
    b1 = run(make_flat_trim(0.83))
    ab = run(predict.Engine(None, halflife=21.0, offset=0.3, trend_gain=0.0).as_strategy())
    print("\nTOTALS over %d training days:" % res["n_days"])
    print("  baseline (B0)        EUR %9.0f   (0.00 pct)" % res["total_baseline_cost"])
    print("  flat -17pct (B1)     EUR %9.0f   (%.2f pct)" % (b1["total_strategy_cost"], b1["gap_closed_pct"]))
    print("  EW ratio  (B2 bar)   EUR %9.0f   (%.2f pct)" % (b2["total_strategy_cost"], b2["gap_closed_pct"]))
    print("  ENGINE (belief-led)  EUR %9.0f   (%.2f pct)" % (res["total_strategy_cost"], res["gap_closed_pct"]))
    print("  engine w/o graph     EUR %9.0f   (%.2f pct)  <- ablation: graph worth %.2f pp" % (
        ab["total_strategy_cost"], ab["gap_closed_pct"], res["gap_closed_pct"] - ab["gap_closed_pct"]))
    print("  breakdown:", {k: round(v) for k, v in res["breakdown"].items()})


if __name__ == "__main__":
    compounding_report()
    path, rows = generate_submission()
    print("\nWrote %d holdout day-plans -> %s" % (len(rows), path))
    print("  sample:", rows[:3], "...", rows[-2:])
