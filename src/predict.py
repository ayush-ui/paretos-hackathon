"""The decision engine (Phase 4) — turns a recommendation into a planned operative total per day.

Design (see docs/TECH_DEBT.md 'Key architectural findings'): at the total level a *global* trim of
the optimiser dominates per-activity structural cuts (no per-activity actuals; cuts double-count the
trim). So the engine is:

    plan(d) = rec_operative(d) * k_regime(d) - offset + trend_adj(d)

where the BELIEF GRAPH governs the three terms:
  - k_regime: an adaptive need/rec trim, **segmented at belief-supplied regime boundaries** (the
    pick-by-light shift) so it adapts to a regime change instead of blending across it.
  - offset: an asymmetric (newsvendor) safety term — overstaffing costs €230 vs ~€41 for a small
    undershoot, so the cost-optimal plan sits slightly BELOW the predicted level (until the SLA tail).
  - trend_adj: a forward correction when need is trending (autumn ramp, L14/L15) — a trailing trim
    underplans a rising series, which matters for the October holdout.

Everything is walk-forward: at decision date D only actuals strictly before the Monday of D's week
are visible (enforced by eval/backtest.Context). No holdout peeking (ANTI_REWARD_HACKING.md).
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from . import data
from .beliefs import BeliefGraph, Belief
from .cost import day_cost


def _ew_mean(pairs, ref_date: str, halflife: float) -> Optional[float]:
    """Exponentially-weighted mean of dated values; most recent weighted highest."""
    if not pairs:
        return None
    decay = 0.5 ** (1.0 / halflife)
    ref = _dt.date.fromisoformat(ref_date)
    num = den = 0.0
    for d, v in pairs:
        age = (ref - _dt.date.fromisoformat(d)).days
        w = decay ** age
        num += w * v
        den += w
    return num / den if den else None


def regime_boundaries(graph: Optional[BeliefGraph]) -> List[str]:
    """Belief-supplied dates where the optimiser's error regime shifts (e.g. pick-by-light).

    Sourced from any picking scale_pct belief that was NOT retired by curation (its claim of a new
    regime survived). Returns sorted unique ISO dates. Empty if no graph / no such belief.
    """
    if graph is None:
        return []
    out = set()
    for b in graph.list():
        if b.kind == "scale_pct" and "Picking" in b.activities and b.status != "retired":
            # the post-event start date the note claims (valid_from already respects captured_on)
            out.add(b.valid_from)
    return sorted(out)


class Engine:
    """Walk-forward staffing engine. Construct once with a curated graph; call plan_cycle per week."""

    def __init__(self, graph: Optional[BeliefGraph] = None, halflife: float = 21.0,
                 offset: float = 0.6, trend_gain: float = 0.5, min_regime_days: int = 4,
                 default_k: float = 0.84, k_window: Optional[int] = None,
                 auto_offset: bool = False):
        self.graph = graph
        self.halflife = halflife
        self.offset = offset          # newsvendor safety subtraction (person-days)
        self.trend_gain = trend_gain  # fraction of detected weekly slope to lead by
        self.min_regime_days = min_regime_days
        self.default_k = default_k
        # --- protective-lean options (off by default => the locked scored path is unchanged) ---
        # k_window: if set, the adaptive trim k uses only the last `k_window` calendar days of history
        #   (recency lean — reacts faster to a rising October ramp than the full EW tail).
        # auto_offset: if True, the newsvendor safety term is grid-searched to minimise cost on the
        #   trailing past window (data-driven best_offset, ported idea from team base_model.best_offset)
        #   instead of the fixed `offset` subtraction.
        self.k_window = k_window
        self.auto_offset = auto_offset
        self.boundaries = regime_boundaries(graph)
        self._trend_active = graph is not None and any(
            b.kind in ("note", "trend") and b.params.get("trend") == "up" and b.status != "retired"
            for b in graph.list()
        )

    def _windowed(self, horizon: str, past_ratios: Dict[str, float]) -> Dict[str, float]:
        """Restrict history to the last `k_window` calendar days before the horizon (recency lean).
        No-op when k_window is None — preserves the locked behaviour."""
        if not self.k_window:
            return past_ratios
        ref = _dt.date.fromisoformat(horizon)
        return {d: r for d, r in past_ratios.items()
                if 0 <= (ref - _dt.date.fromisoformat(d)).days <= self.k_window}

    # --- regime-segmented adaptive trim ---------------------------------------------------
    def _k_for(self, plan_date: str, horizon: str, past_ratios: Dict[str, float]) -> float:
        """Estimate the need/rec trim for a planned day using same-regime history before horizon."""
        past_ratios = self._windowed(horizon, past_ratios)
        # which regime does the planned day fall in? (relative to belief boundaries)
        b_before_plan = max([b for b in self.boundaries if b <= plan_date], default=None)
        # keep only history strictly before the horizon AND on the same side of that boundary
        same = [(d, r) for d, r in past_ratios.items() if d < horizon and
                (b_before_plan is None or d >= b_before_plan)]
        if len(same) >= self.min_regime_days:
            return _ew_mean(same, horizon, self.halflife)
        # not enough post-regime data yet: blend pre-regime k with the belief's expected shift
        all_hist = [(d, r) for d, r in past_ratios.items() if d < horizon]
        base = _ew_mean(all_hist, horizon, self.halflife) if all_hist else self.default_k
        if b_before_plan is not None and base is not None:
            shift = self._belief_shift(b_before_plan)  # expected total-level ratio shift, <=0
            return base + shift
        return base if base is not None else self.default_k

    def _belief_shift(self, boundary: str) -> float:
        """Translate a picking %-cut belief at `boundary` into an expected TOTAL-level ratio shift.

        Picking is ~1/6 of the operative total, so a picking pct cut moves the total ratio by
        roughly pct * picking_share. Conservative, belief-derived prior used only until post-regime
        actuals accumulate. Returns a small non-positive number.
        """
        if self.graph is None:
            return 0.0
        picking_share = 0.16
        worst = 0.0
        for b in self.graph.list():
            if b.kind == "scale_pct" and "Picking" in b.activities and b.valid_from == boundary \
                    and b.status != "retired":
                worst = min(worst, (b.params.get("pct", 0) / 100.0) * picking_share)
        return worst

    # --- trend lead for a rising series ---------------------------------------------------
    def _trend_adj(self, plan_date: str, horizon: str, past_need: Dict[str, float]) -> float:
        if not self._trend_active:
            return 0.0
        # weekly slope of realized need over the trailing ~4 weeks before horizon
        hist = sorted((d, n) for d, n in past_need.items() if d < horizon)
        if len(hist) < 10:
            return 0.0
        recent = hist[-20:]
        xs = [( _dt.date.fromisoformat(d) - _dt.date.fromisoformat(recent[0][0])).days for d, _ in recent]
        ys = [n for _, n in recent]
        n = len(xs)
        mx = sum(xs) / n; my = sum(ys) / n
        denom = sum((x - mx) ** 2 for x in xs)
        if denom == 0:
            return 0.0
        slope_per_day = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
        if slope_per_day <= 0:
            return 0.0  # only lead when genuinely rising
        days_ahead = (_dt.date.fromisoformat(plan_date) - _dt.date.fromisoformat(recent[-1][0])).days
        return self.trend_gain * slope_per_day * days_ahead

    # --- data-driven newsvendor offset (ported idea: team base_model.best_offset) ----------
    def _offset_add(self, horizon: str, past_ratios: Dict[str, float],
                    past_need: Dict[str, float]) -> float:
        """The ADDITIVE safety term applied after the trim. Default: the fixed -offset subtraction.

        With auto_offset, grid-search the additive shift that would have cost LEAST over the trailing
        window — the newsvendor optimum given the asymmetric cost (overstaff €230 vs ~€41 undershoot).
        Walk-forward: uses only history strictly before the horizon. Reconstructs each past day's
        prediction as (rec * its k) from the ratios already exposed by the context.
        """
        if not self.auto_offset:
            return -self.offset
        pr = self._windowed(horizon, {d: r for d, r in past_ratios.items() if d < horizon})
        if len(pr) < self.min_regime_days:
            return -self.offset
        preds, needs = [], []
        for d in sorted(pr):
            need = past_need.get(d)
            ratio = pr[d]
            if need is None or ratio <= 0:
                continue
            rec_op = need / ratio                       # reconstruct the optimiser rec for that day
            preds.append(rec_op * self._k_for(d, horizon, past_ratios))
            needs.append(need)
        if not preds:
            return -self.offset
        lo = min(n - p for p, n in zip(preds, needs)) - 1.0
        hi = max(n - p for p, n in zip(preds, needs)) + 1.0
        best_off, best_cost = -self.offset, float("inf")
        steps = 81
        for i in range(steps):
            off = lo + (hi - lo) * i / (steps - 1)
            c = sum(day_cost(p + off, n) for p, n in zip(preds, needs))
            if c < best_cost:
                best_cost, best_off = c, off
        return best_off

    # --- public: plan one cycle (compatible with eval.backtest strategy signature) --------
    def plan_cycle(self, rec, scored_days: List[str], ctx) -> Dict[str, float]:
        past_ratios = ctx.past_ratios()
        past_need = ctx.past_need()
        off_add = self._offset_add(ctx.horizon, past_ratios, past_need)
        out = {}
        for d in scored_days:
            k = self._k_for(d, ctx.horizon, past_ratios)
            level = rec.operative_total(d) * k
            out[d] = level + off_add + self._trend_adj(d, ctx.horizon, past_need)
        return out

    def as_strategy(self):
        def strat(rec, days, ctx):
            return self.plan_cycle(rec, days, ctx)
        strat.__name__ = f"engine_hl{self.halflife}_off{self.offset}"
        return strat

    # --- explainability: the step-by-step behind one day's number --------------------------
    def explain(self, rec, day: str, ctx) -> Dict:
        """Return every intermediate value behind plan(day) — powers the UI 'why this number' view.

        Pure read-out of the same computation as plan_cycle; no side effects, no future data.
        """
        past_ratios = ctx.past_ratios()
        past_need = ctx.past_need()
        recommended = rec.operative_total(day)
        boundary = max([b for b in self.boundaries if b <= day], default=None)
        same_regime = sorted((d, r) for d, r in past_ratios.items()
                             if d < ctx.horizon and (boundary is None or d >= boundary))
        k = self._k_for(day, ctx.horizon, past_ratios)
        level = recommended * k
        trend = self._trend_adj(day, ctx.horizon, past_need)
        off_add = self._offset_add(ctx.horizon, past_ratios, past_need)
        planned = level + off_add + trend
        return {
            "date": day,
            "recommended": round(recommended, 2),
            "regime_boundary": boundary,
            "history_ratios": {d: round(r, 3) for d, r in same_regime},
            "k": round(k, 4),
            "level": round(level, 2),
            "offset": round(-off_add, 3),  # reported as a subtraction (positive = leaning down)
            "trend_adj": round(trend, 3),
            "planned": round(planned, 2),
        }
