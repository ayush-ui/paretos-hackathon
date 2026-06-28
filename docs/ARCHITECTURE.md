# ARCHITECTURE.md — The compounding decision engine

> Status: PROPOSED (awaiting build). Read DATA_REFERENCE.md + DECISION_LOG_ANALYSIS.md first.

## 0. What we are optimising (don't lose this)
Emit, for each future working day, a single number: **planned operative person-days**. Scored in
money (cost_model.json) against withheld October actuals. The judges reward **the loop** — how we
*represent, trust, and expire knowledge* — not the modelling stack (README §6). So the system must
visibly: **capture** error, **apply** it next cycle, **curate** (promote durable, retire stale).

## 1. Is a knowledge graph appropriate? — YES, but only as ONE layer
Recommendation: **use a knowledge graph as the belief/curation layer, NOT as the predictor.**
- The numeric prediction (how many person-days) is a **forecasting/adjustment** problem →
  best served by a transparent, backtested statistical model, not a graph.
- But "capture WHY plan ≠ reality, decide what to trust and when, retire stale beliefs, resolve
  contradictions" is *exactly* a **typed graph of beliefs**: nodes = rules/beliefs, edges =
  `refines / contradicts / supersedes / scoped-to-activity / triggered-by-event`. This is the part
  the judges score on innovation, and a KG models it natively (L03 ──superseded_by──▶ L11/L12;
  L08 ──contradicts──▶ L09; L02 ──reaffirmed_by──▶ L10).
- **Do NOT reach for Neo4j/heavyweight graph DB** for ~15 notes — it's over-engineering. Use a
  lightweight in-process typed graph (nodes + typed edges, JSON-serialisable). The *pattern* is the
  value, not the database. Keep it swappable.

Verdict: KG = the knowledge representation & governance layer that **gates** the numeric engine.
Hybrid: **statistical adjustment engine governed by a curated belief graph.**

## 2. Component overview
```
            ┌────────────────────────────────────────────────────────────┐
            │                    COMPOUNDING LOOP (per cycle)             │
            │                                                            │
  raw data ─┤  1. INGEST: parse recs, actuals, volumes, decision_log     │
            │  2. LEARN: estimate optimiser error from actuals available  │
            │            *up to this decision date only* (walk-forward)   │
            │  3. BELIEF GRAPH: turn errors + log notes into typed        │
            │       beliefs w/ trust score, scope, validity window        │
            │  4. CURATE: validate each belief vs backtest; promote /     │
            │       demote / retire / resolve-contradictions; expire stale│
            │  5. DECIDE: apply only ACTIVE, TRUSTED beliefs to next      │
            │       cycle's recommendation → planned operative total/day  │
            │  6. SCORE & FEED BACK: when actuals arrive, log realized    │
            │       cost, update belief trust, repeat                     │
            └────────────────────────────────────────────────────────────┘
```

## 3. The numeric engine (engine/)
Target = daily operative total. Decompose the optimiser's recommendation, not reinvent it:
`planned = f(recommendation, volume_signal, calendar, active_beliefs)`.
- **Base trim**: a multiplicative correction of the recommendation (the ~0.84 ratio) estimated
  walk-forward (e.g. trailing-window or exponentially-weighted ratio of realized need / rec).
- **Regime awareness**: allow the ratio to shift at detected change-points (pick-by-light 08-24).
  Belief graph supplies the event date; engine re-estimates post-event.
- **Trend/extrapolation**: for the October holdout, lean on the autumn-ramp belief (L14/L15) — plan
  to the *trend*, not the trailing mean (which underplans a rising series).
- **Asymmetric loss tuning**: because the cost is asymmetric (cheap small undershoot, explosive
  >2.0 SLA), the optimal point estimate is **not** the mean of need — pick the plan that minimises
  expected `day_cost` given the predictive residual distribution. This is a real, principled edge.
- Keep every adjustment **attributable** to a belief (for the frontend "why" view).

## 4. The belief graph (knowledge/)
Node (Belief): `id, source(log|derived), claim, scope(activity|operative), kind(fixed|scale|add|
conditional|trend), params, valid_from, valid_to|null, trust∈[0,1], status(candidate|active|
stale|retired), evidence[]`.
Edge types: `supersedes, contradicts, refines, reaffirms, depends_on_event`.
Curation rules (must be data-driven, not hardcoded verdicts):
- A belief earns trust when applying it **improves backtested cost** on the windows where it's in
  scope; loses trust when it doesn't.
- `contradicts` pair → keep the one with better backtested cost; mark the other retired w/ reason.
- A belief auto-expires (`stale`) when its recent-window backtest cost stops beating "ignore it".
- New evidence (post-event) can `supersede` an old belief and open a new validity window.

## 5. Backtest / scoring harness (eval/)
- Re-implement `scoring.py`'s `day_cost` EXACTLY (see DATA_REFERENCE §8). Unit-test it.
- **Walk-forward only**: for decision date D, train on actuals with date < D's planned week. No peeking.
- Report per-cycle: our cost vs Baseline vs Perfect, and **% of baseline→perfect gap closed**.
- Track the gap **shrinking over cycles** — that curve is the headline deliverable (README §6.2).

## 6. Frontend (later)
Visualise: (a) the belief graph with status/trust over time; (b) per-cycle gap-closed curve;
(c) per-day plan with attribution ("we trimmed X because belief Lnn"). Build engine first.

## 7. Proposed stack
Python (data is CSV/JSON, scoring is Python). Std lib + pandas/numpy; optional networkx for the
graph (or a tiny hand-rolled node/edge dict — preferred, zero-dep, fully controllable). Frontend
TBD (lightweight: Streamlit for speed, or React if we want polish). **Decide stack before §3.**
