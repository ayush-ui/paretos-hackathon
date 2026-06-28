# DATA_REFERENCE.md — Metadata cache for the Helios staffing dataset

> Purpose: a single source of truth so no agent has to re-inspect the raw data.
> Last verified against data: 2026-06-27. If you change/add data, re-verify the numbers in §6.

## 1. The problem in one paragraph
A warehouse (Helios Logistics — DC Rhein-Main) gets a **weekly staffing recommendation**
from a deterministic optimiser (forecast volume ÷ fixed rate card). The optimiser
**systematically overstaffs** (rate card never re-tuned). Each week the planner commits an
actual plan, then **actuals** reveal the true need. We must build a **compounding loop**
that learns the optimiser's error structure week-over-week and emits a better plan. We are
scored in **money** on the **operative person-day total per day** over a **held-out 4-week
window (October 2026)** whose actuals are withheld.

## 2. File map
```
hackathon-dataset/data/
├── recommendations/rec_<decision-Tuesday>.csv   24 files. Raw optimiser plans (incl. 4 holdout).
├── actuals/present_<week-Monday>.csv            Training only. Daily PRESENT_TOTAL person-days.
├── actuals/volumes_<week-Monday>.csv            Training only. Realized PICKS/VOLLPALETTEN/KOMMPALETTEN.
├── clean/recommendations_long.csv               Tidy, training only (20 cycles).
├── clean/present_long.csv                        Tidy actuals (the prediction target).
├── clean/volumes_long.csv                        Tidy forecast vs realized volumes.
├── decision_log.json                            15 planner notes (L01–L15). Messy & unverified.
└── cost_model.json                              The scoring cost function.
```

## 3. Schemas (clean/ — START HERE)
**present_long.csv** — `date, present_total_person_days, present_operative_person_days`
- `present_operative_person_days = present_total_person_days − 8` (admin is a constant 8).
- **`present_operative_person_days` is THE prediction target.**

**volumes_long.csv** — `date, picks_forecast, picks_realized, outbound_forecast,
outbound_realized, inbound_forecast, inbound_realized`
- forecast = what the optimiser planned against; realized = what actually happened.
- inbound = pallets in (PAL_Wareneingang), outbound = full outbound pallets (VollPAL), picks = lines.

**recommendations_long.csv** — `decision_date, planned_week_start, date, activity, group, recommended_person_days`
- `group` ∈ {operative, administrative}. Scoring uses **operative** only.
- 15 operative activities + 4 admin desks (see §5).
- Sum of operative rows per day = optimiser's recommended operative total (what we trim).

## 4. Raw file gotchas (only if you parse raw/ instead of clean/)
- **Semicolon-delimited**, wide format (1 col per calendar day, Mon–Sun).
- **German decimals**: `8,9` means 8.9. Replace `,`→`.`.
- Weekends & public holidays = all-zero columns. **Holidays that close the floor:**
  **2026-05-25** (Whit Mon), **2026-06-04** (Corpus Christi), **2026-10-03** (Unity Day, in holdout).
- `recommendations/` filename date = the **decision Tuesday**; planned week = the following Mon–Fri.
- `actuals/present_*` & `volumes_*` filename date = the planned week's **Monday**.
- `present_*`: `DATUM` (DD.MM.YYYY), `PRESENT_TOTAL`; `FORECAST_PL` is an empty legacy column — ignore.
- `volumes_*`: dates are **mixed German/English long form** on purpose; `PICKS, VOLLPALETTEN, KOMMPALETTEN`.

## 5. The 19 activities
**Operative (15, scored):** Unloading, Receiving, Putaway, Picking, Staging, Loading,
Replenishment / relocation, Transit drivers, Yard shunting, Team leads, Pick QA,
Co-Packing line, VNA replenishment, Returns / QC, Aisle maintenance.
**Administrative (4, constant 8 total, NOT scored):** Control room, Outbound office,
Inbound office, Inventory.

## 6. Verified key numbers (training overlap: 98 days, 2026-05-18 → 2026-10-02)
- Mean optimiser operative total ≈ **64.0** person-days/day; mean realized need ≈ **53.6**.
- Optimiser **overstaffs by ≈10.4 person-days/day**; mean realized/recommended ratio ≈ **0.838**
  (i.e. true need ≈ 84% of the optimiser plan; a flat ~16% trim is the crude baseline).
- **BASELINE cost** (staff exactly the optimiser) over the 98 training days ≈ **€234,600**.
- **Flat −17% trim** cost ≈ **€19,656** → closes ≈ **91.6%** of the baseline→perfect gap on training.
  (README quotes ~86% on the holdout. The point: the easy ~86–92% is NOT where you win.)
- Monthly need/rec ratio: May .845, Jun .843, Jul .851, Aug .835, **Sep .818**, Oct .841.
  The Sep dip ≈ pick-by-light cutting picking, partly offset by the autumn outbound ramp.
- Weekday ratios are flat (~.83–.84) at the **aggregate** level — weekday signal lives at the
  **activity** level (see decision log L04/L05/L07), not the total.

## 6b. ⚠️ CRITICAL CONSTRAINT — actuals are TOTAL-ONLY
Actuals (`present_*`) give only the **whole-site operative total per day**. There are **NO
per-activity actuals.** The decision-log notes (L01–L15) are mostly *per-activity* claims, but
we can only validate them through (a) their effect on the daily total and (b) the realized
**volume** signal. Implication: the prediction model targets the **daily operative total**;
the decision log supplies *structural hypotheses* about the error, not directly-fittable labels.
Empirically confirmed at the total level (2026-06-27):
- Pick-by-light: need/rec ratio **0.845 → 0.82** after 2026-08-24 (real; modest at total level as
  picking is 1 of ~15 activities).
- L08 vs L09: late-summer (W30–33) ratio **0.848 > 0.838 overall** → need ran *higher*, so **L09
  (needed more) beats L08 (cut 15%)**. L08 is a trap.
- Autumn ramp: realized picks Jul **8958** → Aug **9468** → Sep **9874** (clear uptrend → October
  likely higher; a backward-looking average will underplan the holdout).

## 7. Timeline
24 weekly cycles. **20 training** (decision 2026-05-12 … 2026-09-22) with actuals; **4 holdout**
(decision 2026-09-29, 10-06, 10-13, 10-20 → planned weeks across October) with **actuals withheld**.

## 8. Cost model (cost_model.json) — the scoring function
Per operative person-day, against realized need N (= present_total − 8):
- **Overstaff** (plan > N): `(plan − N) × €230` (idle wage).
- **Understaff** (plan < N): `(N − plan) × €41.4` (18% overtime premium) **PLUS**, for the
  shortfall *beyond 2.0 person-days*, `(shortfall − 2.0) × €600` (SLA/late-truck penalty).
- **Asymmetry:** a small deliberate undershoot (≤2.0) is cheaper than a safe overshoot;
  past 2.0 it explodes. **Cut toward the truth, not past it.**

```python
def day_cost(plan, need):
    if plan >= need:
        return (plan - need) * 230.0
    short = need - plan
    c = short * 41.4
    if short > 2.0:
        c += (short - 2.0) * 600.0
    return c
```
- **Submission format:** `date,planned_operative_person_days` scored by `SOLUTION/scoring.py`
  (facilitator-held; replicate it exactly in our harness).
- Anchors: **Baseline** = raw optimiser; **Perfect** = realized need (unreachable floor).
