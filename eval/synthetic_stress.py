"""SYNTHETIC stress-test — run OUR engine through what-if regime worlds it never saw.

The real holdout is a single October. One draw of one regime can't show whether the engine is
ROBUST or merely lucky. So we synthesise alternative Octobers — autumn ramp, heat drag, flu-absence
productivity hit, a stronger pick-by-light efficiency jump — feed each through the *frozen* engine
(trained only on real data before the block), and score with our one cost function (src.cost).

The generator MODEL is ported from the teammate's `engine/synthetic.py` (re-implemented here, not
imported — their folder is read-only and depends on pandas/sqlite). Every knob is grounded:
  * base relationship + noise from the REAL measured data (ratio 1.195 -> 0.837, residual std ~1.5),
  * ramp / heat / pick-by-light from the planner notes (L15 / L09 / L11-L12),
  * the flu / weather windows are CLEARLY-LABELLED what-if knobs, not claims about the real data.

This is SYNTHETIC evidence (robustness across regimes); the real-data ablation in eval/submit.py and
eval/validate.py remains the PRIMARY evidence. Deterministic given a seed.

Run: python3 eval/synthetic_stress.py
"""
from __future__ import annotations

import datetime as _dt
import os
import sys
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from src.cost import day_cost  # noqa: E402
from eval.backtest import Context  # noqa: E402

# --- measured constants (the same numbers our real engine and docs use) -------------------
MEASURED = {
    "base_rate": 0.837,   # actual operative = optimiser x 0.837 (optimiser overstaffs ~19.5%)
    "noise_std": 1.5,     # daily residual std after correction (person-days), measured
}
PICK_BY_LIGHT = "2026-08-24"

# A what-if multiplier on need over a window, each with a one-line, honest rationale.
WEATHER = {
    "none":     (1.00, "no weather event"),
    "heatwave": (1.06, "heat slows the floor (note L09) -> ~6% more hours for the same volume"),
    "coldsnap": (1.05, "cold-snap demand pull-forward -> ~5% more outbound to staff for"),
}

# The regime worlds we stress the engine through. ramp_pct compounds over a 4-week month;
# heat/flu are productivity-drag multipliers over a window; pbl_factor is the picking efficiency
# gain diluted to the whole-site total (1.0 = none, <1 = pickers faster -> less need).
ENGINE_CFG = dict(halflife=21.0, offset=0.3, trend_gain=0.4)

WORLDS: Dict[str, Dict] = {
    "autumn ramp":      dict(ramp_pct=8,  drag_pct=0,  drag_window=[], weather="none",
                             pbl_factor=0.97, noise=1.5,
                             story="The base case from note L15: demand ramps ~8% into October."),
    "strong ramp":      dict(ramp_pct=15, drag_pct=0,  drag_window=[], weather="none",
                             pbl_factor=0.97, noise=1.5,
                             story="A harder ramp (~15%) — the SLA-cliff risk the protective lean guards."),
    "heat drag":        dict(ramp_pct=6,  drag_pct=6,  drag_window="first2w", weather="heatwave",
                             pbl_factor=0.97, noise=1.8,
                             story="An unseasonal heatwave (note L09) slows throughput for two weeks."),
    "flu absence":      dict(ramp_pct=8,  drag_pct=9,  drag_window="mid2w", weather="none",
                             pbl_factor=0.97, noise=2.0,
                             story="A flu wave: ~9% more hours needed for two weeks to cover the same work."),
    "pick-by-light":    dict(ramp_pct=8,  drag_pct=0,  drag_window=[], weather="none",
                             pbl_factor=0.93, noise=1.5,
                             story="The pick-by-light rollout lands harder (notes L11/L12): pickers ~7% faster."),
}


def _resolve_window(spec, dates: List[str]) -> set:
    """Turn a window spec ('first2w' | 'mid2w' | list of dates) into a set of ISO dates."""
    if isinstance(spec, (list, tuple)):
        return set(spec)
    n = len(dates)
    if spec == "first2w":
        return set(dates[: min(10, n)])
    if spec == "mid2w":
        lo = max(0, n // 2 - 5)
        return set(dates[lo: lo + 10])
    return set()


def generate(dates: List[str], optimiser: Dict[str, float], world: Dict,
             seed: int = 7) -> Tuple[Dict[str, float], List[Tuple[str, str, str]]]:
    """Synthetic ACTUAL operative need for `dates`, given the real optimiser recs.

    need[d] = optimiser[d] * base_rate * ramp(week) * drag(window) * weather * pbl + N(0, noise)
    Returns (need_by_date, provenance) where provenance explains each component + its source.
    """
    rng = np.random.default_rng(seed)
    ramp_pct = world.get("ramp_pct", 0)
    drag_pct = world.get("drag_pct", 0)
    drag = _resolve_window(world.get("drag_window", []), dates)
    weather = world.get("weather", "none")
    pbl_factor = world.get("pbl_factor", 0.97)
    noise_std = world.get("noise", MEASURED["noise_std"])
    w_mult, w_reason = WEATHER.get(weather, (1.0, ""))
    weekly_ramp = (1.0 + ramp_pct / 100.0) ** (1.0 / 4.0)

    d0 = _dt.date.fromisoformat(dates[0])
    need: Dict[str, float] = {}
    for ds in dates:
        week_idx = (_dt.date.fromisoformat(ds) - d0).days // 7
        ramp = weekly_ramp ** week_idx
        drag_f = (1.0 + drag_pct / 100.0) if ds in drag else 1.0
        weather_f = w_mult if weather != "none" else 1.0
        pbl = pbl_factor if ds >= PICK_BY_LIGHT else 1.0
        base = optimiser[ds] * MEASURED["base_rate"] * ramp * drag_f * weather_f * pbl
        need[ds] = max(base + float(rng.normal(0, noise_std)), 0.0)

    prov = [
        ("Base relationship", "need = optimiser x 0.837",
         "measured: optimiser overstaffs ~19.5% (ratio 1.195) across 98 real days"),
        ("Daily noise", f"+/- Normal(0, {noise_std} pd)", "measured residual std ~1.5 pd"),
        ("Autumn ramp", f"+{ramp_pct}% per 4-week month, compounding", "planner note L15"),
        ("Pick-by-light", f"picking need x{pbl_factor} from {PICK_BY_LIGHT}", "notes L11/L12 (diluted to total)"),
    ]
    if drag_pct:
        prov.append(("Productivity drag", f"+{drag_pct}% over {len(drag)} days",
                     "what-if window (heat note L09 / flu) — labelled, not from data"))
    if weather != "none":
        prov.append(("Weather event", f"{weather}: need x{w_mult}", w_reason + "  [labelled what-if]"))
    return need, prov


def _flat_trim(optimiser: Dict[str, float], dates: List[str], k: float = 0.83) -> Dict[str, float]:
    """A blind constant trim — the hindsight-oracle flat-17% (k chosen over all training, NOT a fair
    walk-forward number). Reported for reference only; the fair comparator is the ablation engine."""
    return {d: optimiser[d] * k for d in dates}


def run_world(name: str, world: Dict, cutoff: str = "2026-10-01",
              seed: int = 7, engine_cfg: Optional[Dict] = None) -> Dict:
    """Freeze at `cutoff` (real training only), then score OUR engine vs the NO-KNOWLEDGE ablation
    engine (same adaptive trim, but no belief graph and no trend lead) against the synthetic actuals
    for the October block. The ablation is the walk-forward-fair 'naive' comparator — it isolates
    exactly what the belief/trend knowledge layer adds, the same way the real-data ablation does.
    A hindsight flat-0.83 trim is reported alongside for reference. Lower cost / higher gap = better.
    """
    cfg = engine_cfg or ENGINE_CFG
    present = data.load_present()
    recs = data.load_recommendations()
    volumes = data.load_volumes()
    rec_op = {d: t for r in recs.values()
              for d, t in r.operative_totals().items() if data.is_working_day(d)}

    # the October block from the real holdout recommendations
    block = sorted(d for r in recs.values() for d in r.dates
                   if d >= cutoff and data.is_working_day(d) and d in rec_op)
    optimiser = {d: rec_op[d] for d in block}

    g = curate.build_graph()
    curate.curate(g, present, recs, as_of=cutoff)   # only knowledge known before the block
    engine = predict.Engine(g, **cfg)
    # ablation: identical config minus the knowledge layer (no graph -> no regime segmentation,
    # trend_gain=0 -> no autumn-ramp lead). This is our established real-data ablation comparator.
    naive = predict.Engine(None, halflife=cfg["halflife"], offset=cfg["offset"], trend_gain=0.0)

    def decision_for(d):
        for dd, rec in recs.items():
            if d in rec.dates:
                return dd
        return None

    frozen = Context(present, volumes, rec_op, cutoff)
    plan = {d: engine.plan_cycle(recs[decision_for(d)], [d], frozen)[d] for d in block}
    naive_plan = {d: naive.plan_cycle(recs[decision_for(d)], [d], frozen)[d] for d in block}
    flat = _flat_trim(optimiser, block)
    need, prov = generate(block, optimiser, world, seed)

    bc = sum(day_cost(optimiser[d], need[d]) for d in block)
    pc = sum(day_cost(plan[d], need[d]) for d in block)
    nc = sum(day_cost(naive_plan[d], need[d]) for d in block)
    fc = sum(day_cost(flat[d], need[d]) for d in block)
    gap = lambda c: (bc - c) / bc * 100 if bc else 0.0
    return {
        "world": name, "story": world.get("story", ""), "n_days": len(block),
        "optimiser_cost": bc, "engine_cost": pc, "naive_cost": nc, "flat_trim_cost": fc,
        "engine_gap_pct": gap(pc), "naive_gap_pct": gap(nc), "flat_trim_gap_pct": gap(fc),
        "engine_beats_naive": pc < nc,
        "engine_mae": sum(abs(plan[d] - need[d]) for d in block) / len(block),
        "understaffed": sum(1 for d in block if plan[d] < need[d]),
        "provenance": prov,
    }


def run_all(seed: int = 7, engine_cfg: Optional[Dict] = None) -> List[Dict]:
    return [run_world(name, world, seed=seed, engine_cfg=engine_cfg)
            for name, world in WORLDS.items()]


if __name__ == "__main__":
    print("SYNTHETIC stress-test — frozen engine vs the no-knowledge ablation across regime worlds")
    print("(synthetic evidence; the real-data ablation in eval/submit.py remains primary)\n")
    print("  %-15s %8s %9s %7s   %s" % ("world", "engine", "ablation", "beats?", "gap eng/abl/flat"))
    for r in run_all():
        print("  %-15s €%6.0f  €%6.0f   %-5s   %5.1f%% / %5.1f%% / %5.1f%%" % (
            r["world"], r["engine_cost"], r["naive_cost"],
            "yes" if r["engine_beats_naive"] else "NO",
            r["engine_gap_pct"], r["naive_gap_pct"], r["flat_trim_gap_pct"]))
    print("\n(ablation = our engine minus the belief graph + trend lead; flat = hindsight 0.83 oracle)")
