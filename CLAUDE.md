# CLAUDE.md — Project index (read this first)

Hackathon: **Compounding Decisions — warehouse staffing.** Build a loop that learns the optimiser's
weekly error, curates that knowledge (promote durable / retire stale), and emits a cheaper staffing
plan. Scored in € on the **daily operative person-day total** over a withheld October holdout.

## Read in this order
1. `hackathon-dataset/README.md` — the official brief.
2. `docs/DATA_REFERENCE.md` — data schemas, gotchas, verified key numbers (the metadata cache).
3. `docs/DECISION_LOG_ANALYSIS.md` — the 15 planner notes classified (claims to verify).
4. `docs/ARCHITECTURE.md` — proposed engine (incl. the knowledge-graph decision).
5. `docs/ROADMAP.md` — phased plan + checklists.
6. `docs/ANTI_REWARD_HACKING.md` — **integrity guardrails (mandatory).**
7. `docs/TECH_DEBT.md` — known shortcuts/debts.
8. `docs/APP_PLAN.md` — backend+frontend plan (FastAPI + React/Vite/TS + React Flow).
9. `docs/LLM_INTEGRATION.md` — optional Claude layer (note parsing + explanations); off by default.
10. `docs/MERGE_PLAN.md` — two-team merge: golden baselines, what's done/pending/dropped + rationale.
11. `PROGRESS.md` — live status; update each session.

## Non-negotiables
- **Walk-forward only**; never touch/infer the holdout actuals (ANTI_REWARD_HACKING.md).
- Derive adjustments from data — no hardcoded verdicts.
- Test the cost function and the leakage boundary.
- Beat **B2 (EW trailing ratio)**, not just the raw baseline.

## Conventions
- Code under `src/`, eval harness under `eval/`, tests under `tests/`. Python.
- Update PROGRESS.md + the relevant doc whenever state changes; log shortcuts in TECH_DEBT.md.
