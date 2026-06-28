"""Scoring / cost model.

Exact replication of the facilitator scoring described in README §5 and cost_model.json.
This is THE measuring stick — keep the cost function in exactly one place so the whole project
(backtest, ablations, submission scoring) shares identical semantics. See docs/DATA_REFERENCE.md §8.

Per operative person-day, against the realized operative need N (= present_total - 8):
  - Overstaff (plan >= N):  (plan - N) * 230            (idle wage, full waste)
  - Understaff (plan < N):  short * 41.4                (18% overtime premium on the shortfall)
                            + max(0, short - 2.0) * 600 (SLA penalty beyond the 2.0 tolerance)

Admin (the constant 8) is excluded; we always staff it and it is not scored.
"""
from __future__ import annotations

from typing import Dict, Iterable, Mapping, Tuple

# --- cost_model.json constants (single source of truth) -------------------------------------
REGULAR_COST_PER_PERSON_DAY = 230.0
IDLE_COST_PER_PERSON_DAY = 230.0          # overstaffing: surplus person-day paid but idle
OVERTIME_PREMIUM_PCT = 18.0               # understaffing: premium on the shortfall
OVERTIME_COST_PER_PERSON_DAY = REGULAR_COST_PER_PERSON_DAY * OVERTIME_PREMIUM_PCT / 100.0  # 41.4
SLA_TOLERANCE_PERSON_DAYS = 2.0           # shortfall below this is absorbed cheaply
SLA_PENALTY_PER_PERSON_DAY = 600.0        # per short person-day beyond the tolerance


def day_cost(plan: float, need: float) -> float:
    """Excess cost (EUR) of staffing ``plan`` operative person-days when ``need`` were required.

    Returns 0.0 only at plan == need (the per-day 'perfect' floor). Always >= 0.
    """
    if plan >= need:
        return (plan - need) * IDLE_COST_PER_PERSON_DAY
    short = need - plan
    cost = short * OVERTIME_COST_PER_PERSON_DAY
    if short > SLA_TOLERANCE_PERSON_DAYS:
        cost += (short - SLA_TOLERANCE_PERSON_DAYS) * SLA_PENALTY_PER_PERSON_DAY
    return cost


def score_plan(plan: Mapping[str, float], need: Mapping[str, float]) -> float:
    """Total cost over the dates present in ``need``. ``plan`` must cover every needed date.

    Raises KeyError if a needed date is missing from ``plan`` — we never silently skip a scored day.
    """
    return sum(day_cost(plan[d], need[d]) for d in need)


def gap_closed_pct(strategy_cost: float, baseline_cost: float, perfect_cost: float = 0.0) -> float:
    """Percentage of the baseline->perfect gap closed by a strategy. 100% == perfect, 0% == baseline.

    >100% is possible in principle but here perfect == 0, so the formula reduces to
    (baseline - strategy) / baseline * 100.
    """
    denom = baseline_cost - perfect_cost
    if denom <= 0:
        return 0.0
    return (baseline_cost - strategy_cost) / denom * 100.0


def cost_breakdown(plan: Mapping[str, float], need: Mapping[str, float]) -> Dict[str, float]:
    """Diagnostic split of total cost into over/under/SLA components (for reporting, not scoring)."""
    over = under_premium = sla = 0.0
    over_days = under_days = sla_days = 0
    for d in need:
        p, n = plan[d], need[d]
        if p >= n:
            over += (p - n) * IDLE_COST_PER_PERSON_DAY
            if p > n:
                over_days += 1
        else:
            short = n - p
            under_premium += short * OVERTIME_COST_PER_PERSON_DAY
            under_days += 1
            if short > SLA_TOLERANCE_PERSON_DAYS:
                sla += (short - SLA_TOLERANCE_PERSON_DAYS) * SLA_PENALTY_PER_PERSON_DAY
                sla_days += 1
    return {
        "total": over + under_premium + sla,
        "overstaff_cost": over,
        "understaff_premium_cost": under_premium,
        "sla_penalty_cost": sla,
        "overstaffed_days": over_days,
        "understaffed_days": under_days,
        "sla_breach_days": sla_days,
    }
