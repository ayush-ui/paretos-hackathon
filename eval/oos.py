"""Out-of-sample freeze-and-predict harness — the honest dress rehearsal for the October holdout.

Train through a cutoff, FREEZE the model, then predict the block of weeks after it using only data
strictly before the cutoff (no mid-block relearn), and score it. This is exactly how the real
October holdout works, and it is a stricter test than the per-cycle walk-forward backtest (which
gets to re-learn each week). Adopted from the teammate's protocol; scored by our one cost function.

Default cutoff 2026-09-01 predicts September (which has actuals), giving a real OOS number.

Run: python3 eval/oos.py
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from typing import Dict, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from src.cost import day_cost  # noqa: E402
from eval.backtest import Context  # noqa: E402

ENGINE_CFG = dict(halflife=21.0, offset=0.3, trend_gain=0.4)


def _next_month_end(cutoff: str) -> str:
    d = _dt.date.fromisoformat(cutoff)
    # predict to the end of the calendar month the cutoff falls into (the validation block)
    nxt = (d.replace(day=28) + _dt.timedelta(days=4)).replace(day=1)
    return nxt.isoformat()


def run_oos(cutoff: str = "2026-09-01", block_end: Optional[str] = None, use_llm: bool = False,
            engine_cfg: Optional[Dict] = None) -> Dict:
    """Freeze at `cutoff`, predict [cutoff, block_end), score vs actuals where available."""
    cfg = engine_cfg or ENGINE_CFG
    block_end = block_end or _next_month_end(cutoff)
    present = data.load_present()
    recs = data.load_recommendations()
    volumes = data.load_volumes()
    rec_op = {d: t for r in recs.values()
              for d, t in r.operative_totals().items() if data.is_working_day(d)}

    g = curate.build_graph(use_llm=use_llm)
    curate.curate(g, present, recs, as_of=cutoff)        # only knowledge captured before the cutoff
    engine = predict.Engine(g, **cfg)

    def decision_for(d):
        for dd, rec in recs.items():
            if d in rec.dates:
                return dd
        return None

    days = sorted(d for d in present if cutoff <= d < block_end and data.is_working_day(d))
    frozen = Context(present, volumes, rec_op, cutoff)   # horizon fixed at cutoff => only <cutoff data
    plan, base, need = {}, {}, {}
    for d in days:
        rec = recs[decision_for(d)]
        plan[d] = engine.plan_cycle(rec, [d], frozen)[d]
        base[d] = rec_op[d]
        need[d] = present[d]

    bc = sum(day_cost(base[d], need[d]) for d in days)
    pc = sum(day_cost(plan[d], need[d]) for d in days)
    return {
        "cutoff": cutoff, "block_end": block_end, "n_days": len(days),
        "baseline_cost": bc, "plan_cost": pc,
        "gap_closed_pct": (bc - pc) / bc * 100 if bc else 0.0,
        "mae": sum(abs(plan[d] - need[d]) for d in days) / len(days) if days else 0.0,
        "understaffed_days": sum(1 for d in days if plan[d] < need[d]),
    }


if __name__ == "__main__":
    for label, ul in (("hint fallback", False), ("LLM-first", True)):
        r = run_oos(use_llm=ul)
        print(f"OOS September (frozen at {r['cutoff']}) — {label}: "
              f"{r['gap_closed_pct']:.1f}% gap  €{r['plan_cost']:,.0f}  "
              f"MAE {r['mae']:.2f}  understaffed {r['understaffed_days']}/{r['n_days']}")
