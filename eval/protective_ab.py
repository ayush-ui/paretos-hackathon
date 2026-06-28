"""A/B the protective-October-lean engine options against the adoption gate.

Our frozen Sep OOS plan understaffs 16/22 days (within tolerance, but near the €600 SLA cliff if
October ramps higher than September). Two opt-in protective levers (both OFF by default, so the locked
scored path is untouched):
  * k_window  — the adaptive trim uses only the last N days of history (recency lean, reacts faster).
  * auto_offset — grid-search the newsvendor safety shift that minimises cost on the trailing window
                  (data-driven best_offset, ported idea from team base_model.best_offset).

ADOPTION GATE (from the merge brief): adopt ONLY if a variant holds >=93% train AND >=95% OOS-Sep,
OR strictly improves OOS-Sep WITHOUT a train regression. Otherwise keep the default and log it.

Run: python3 eval/protective_ab.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate, predict  # noqa: E402
from eval.backtest import run  # noqa: E402
from eval.oos import run_oos  # noqa: E402

BASE = dict(halflife=21.0, offset=0.3, trend_gain=0.4)
VARIANTS = {
    "DEFAULT (locked)": dict(),
    "recent-30d k": dict(k_window=30),
    "recent-45d k": dict(k_window=45),
    "auto_offset": dict(auto_offset=True),
    "recent-30d k + auto_offset": dict(k_window=30, auto_offset=True),
    "recent-45d k + auto_offset": dict(k_window=45, auto_offset=True),
}
TRAIN_BAR, OOS_BAR = 93.0, 95.0


def evaluate():
    present, recs = data.load_present(), data.load_recommendations()
    rows = []
    default_oos = None
    for name, extra in VARIANTS.items():
        cfg = {**BASE, **extra}
        g = curate.build_graph()
        curate.curate(g, present, recs)
        train = run(predict.Engine(g, **cfg).as_strategy())["gap_closed_pct"]
        r = run_oos(cutoff="2026-09-01", use_llm=False, engine_cfg=cfg)
        if name.startswith("DEFAULT"):
            default_oos = r["gap_closed_pct"]
        rows.append({"name": name, "train": train, "oos": r["gap_closed_pct"],
                     "oos_cost": r["plan_cost"], "understaffed": r["understaffed_days"], "cfg": cfg})
    for row in rows:
        passes_abs = row["train"] >= TRAIN_BAR and row["oos"] >= OOS_BAR
        improves_oos = (row["oos"] > default_oos + 1e-9) and (row["train"] >= TRAIN_BAR - 1e-9)
        row["adopt"] = passes_abs or improves_oos
    return rows


if __name__ == "__main__":
    rows = evaluate()
    print("Protective-lean A/B (adopt iff train>=93%% AND OOS>=95%%, or improves OOS w/o train regression)\n")
    print("  %-30s %8s %8s %12s  %s" % ("variant", "train%", "OOS%", "OOS €/und", "verdict"))
    for r in rows:
        print("  %-30s %7.2f%% %7.1f%%  €%5.0f/%2d   %s" % (
            r["name"], r["train"], r["oos"], r["oos_cost"], r["understaffed"],
            "ADOPT" if r["adopt"] else "reject"))
    adopt = [r for r in rows if r["adopt"] and not r["name"].startswith("DEFAULT")]
    print("\n=>", "ADOPT: " + ", ".join(r["name"] for r in adopt) if adopt
          else "No variant clears the gate — keep the DEFAULT scored path (negative result logged).")
