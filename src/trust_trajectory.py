"""Shadow-trust trajectory — a legible week-by-week trust curve per belief, for the cockpit.

The CURATION layer (src/curate.py) is the engine's real governance: forward-pruning that retires
net-harmful beliefs and promotes helpers. It is binary-ish per run and it powers the ablation, so we
do NOT touch it. This module is pure OBSERVABILITY layered on top: it replays the decisions
walk-forward and, each week, asks "did this belief HELP this week?" — then smooths that into a trust
trajectory with an EWMA:

    trust_w = 0.6 * trust_{w-1} + 0.4 * helped_this_week          (helped in [0,1])

"helped_this_week" is measured honestly at the ENGINE level: retire the belief, re-plan that single
week with only data known by then, and compare cost on that week's scored days. Lower cost with the
belief in => it helped (1.0); higher => it hurt (0.0); negligible => neutral (0.5). The result is a
smooth, jury-readable curve showing trust accruing as evidence confirms a belief and decaying as it
goes stale — the visible face of "compounding". Walk-forward; no holdout actuals (only training weeks
have outcomes, so the trajectory spans the training period).
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from . import data, curate, predict
from .cost import score_plan
from eval.backtest import Context

ALPHA = 0.4               # EWMA weight on this week's evidence (0.6 on the carried-forward trust)
INIT_TRUST = 0.5          # a fresh belief starts neutral
HELP_THRESHOLD = 25.0     # € swing on the week below which we call the belief neutral this week


def _monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def _week_cost(engine: predict.Engine, rec, scored: List[str], ctx, present) -> float:
    plan = engine.plan_cycle(rec, scored, ctx)
    return score_plan(plan, {d: present[d] for d in scored})


def build_trajectories(halflife: float = 21.0, offset: float = 0.3, trend_gain: float = 0.4,
                       present=None, recs=None, volumes=None) -> Dict:
    """Return {belief_id: [{week, trust, helped, delta_eur, n_days, status}]} plus a small summary.

    helped in {0.0, 0.5, 1.0}; trust is the EWMA. Beliefs not yet captured in a given week are absent
    from that week's points (the curve starts when the belief exists)."""
    present = present if present is not None else data.load_present()
    recs = recs or data.load_recommendations()
    volumes = volumes if volumes is not None else data.load_volumes()
    rec_op_by_date = {d: t for r in recs.values()
                      for d, t in r.operative_totals().items() if data.is_working_day(d)}

    trajectories: Dict[str, List[Dict]] = {}
    trust_prev: Dict[str, float] = {}

    for dd in sorted(recs):
        rec = recs[dd]
        scored = [d for d in rec.dates if data.is_working_day(d) and d in present]
        if not scored:
            continue  # holdout week — no outcome to learn from
        week = _monday(dd)
        g = curate.build_graph()
        curate.curate(g, present, recs, as_of=week)
        engine = predict.Engine(g, halflife=halflife, offset=offset, trend_gain=trend_gain)
        ctx = Context(present, volumes, rec_op_by_date, week)
        base_cost = _week_cost(engine, rec, scored, ctx, present)

        for b in g.list():
            if b.valid_from > week:
                continue  # not captured yet — no point on the curve this week
            # measure marginal € of this belief on THIS week by retiring it and re-planning
            if b.status == "retired":
                helped, delta = 0.0, 0.0
            else:
                saved = b.status
                b.status = "retired"
                eng_wo = predict.Engine(g, halflife=halflife, offset=offset, trend_gain=trend_gain)
                cost_wo = _week_cost(eng_wo, rec, scored, ctx, present)
                b.status = saved
                delta = cost_wo - base_cost          # >0 => belief lowered cost this week
                if delta > HELP_THRESHOLD:
                    helped = 1.0
                elif delta < -HELP_THRESHOLD:
                    helped = 0.0
                else:
                    helped = 0.5
            prev = trust_prev.get(b.id, INIT_TRUST)
            trust = (1 - ALPHA) * prev + ALPHA * helped
            trust_prev[b.id] = trust
            trajectories.setdefault(b.id, []).append({
                "week": week, "trust": round(trust, 4), "helped": helped,
                "delta_eur": round(delta), "n_days": len(scored), "status": b.status,
            })

    summary = {
        bid: {
            "final_trust": pts[-1]["trust"],
            "weeks": len(pts),
            "peak_trust": round(max(p["trust"] for p in pts), 4),
            "ever_helped": any(p["helped"] == 1.0 for p in pts),
            "ever_hurt": any(p["helped"] == 0.0 and p["status"] != "retired" for p in pts),
        }
        for bid, pts in trajectories.items()
    }
    return {"trajectories": trajectories, "summary": summary,
            "params": {"alpha": ALPHA, "init_trust": INIT_TRUST, "help_threshold": HELP_THRESHOLD}}


if __name__ == "__main__":
    out = build_trajectories()
    print("SHADOW-TRUST TRAJECTORIES (EWMA: trust = 0.6*old + 0.4*helped)\n")
    print("  belief  weeks  final  peak  helped?  hurt?")
    for bid in sorted(out["summary"]):
        s = out["summary"][bid]
        print("  %-6s  %4d  %5.2f  %5.2f   %-5s   %-5s" % (
            bid, s["weeks"], s["final_trust"], s["peak_trust"],
            "yes" if s["ever_helped"] else "no", "yes" if s["ever_hurt"] else "no"))
    # show one belief's curve
    for bid in ("L11", "L08"):
        if bid in out["trajectories"]:
            print(f"\n  {bid} curve:", " ".join(
                f"{p['week'][5:]}:{p['trust']:.2f}" for p in out["trajectories"][bid]))
