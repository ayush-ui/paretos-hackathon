# ROADMAP.md — Phased implementation plan

Legend: [ ] todo · [~] in progress · [x] done · [!] blocked. Keep PROGRESS.md as the live status.

## Phase 0 — Understand & scaffold  [~]
- [x] Read README, data, cost & decision log; verify key numbers.
- [x] Write DATA_REFERENCE, DECISION_LOG_ANALYSIS, ARCHITECTURE, ROADMAP, CHECKLIST, ANTI_REWARD_HACKING.
- [ ] Confirm stack (Python) and scope with user.
- [ ] `git init` + first commit of docs (ask user first).

## Phase 1 — Foundation: data + scoring (the honest measuring stick)  [x]
- [x] `src/data.py`: loaders for clean/ + raw/ parser w/ German-decimal + holiday handling.
- [x] `src/cost.py`: exact `day_cost` + total scorer; replicates README/cost_model semantics.
- [x] `tests/test_cost.py` (+ test_data.py): asymmetry & 2.0 SLA boundary; raw==clean. 18 pass.
- [x] `eval/backtest.py`: walk-forward harness w/ enforced info horizon; gap-closed reporting.
- [x] Reproduced anchors exactly: baseline €234,600, flat-17% €19,656 (91.6%).

## Phase 2 — Baseline optimisers (beat-this ladder)  [x]
- [x] B0 baseline (€234,600). B1 flat-17% (91.6%). B2 EW trailing ratio (hl14 → **91.0%**).
- [x] Locked. Everything below must beat **B2 = 91.0%**, not just B0.
- NOTE: best global constant k=0.83 → 91.6% only; remaining headroom needs per-day prediction
  (regime/weekday/trend) + asymmetric-loss tail management, not a better constant.

## Phase 3 — Belief graph + curation  [x]
- [x] `src/beliefs.py`: Belief node + typed edges, JSON serialise, validity windows, apply-to-rec.
- [x] Ingest decision_log.json → candidate beliefs (captured_on respected as valid_from).
- [x] `src/curate.py`: data-driven trust via walk-forward marginal cost; supersession + pruning.
- [x] Auto-retires the L08 trap and expires stale L03 via supersession — **no hardcoded verdicts**.
- NOTE: per-activity structural cuts double-count the global trim (TECH_DEBT) → graph instead
  supplies regime boundaries + governance + trend, which is where its measured value comes from.

## Phase 4 — Decision engine w/ asymmetric loss  [x]
- [x] `src/predict.py`: regime-segmented adaptive trim + newsvendor offset + trend lead.
- [x] Belief-supplied regime boundary (2026-08-25) drives the time-varying trim.
- [x] `eval/submit.py`: compounding report + `submissions/submission.csv` (20 holdout days).
- [x] Beats B2 (91.03% → 93.03%); graph ablation confirms +1.36pp from the belief layer.

## Phase 5 — Validation & anti-overfit  [x]
- [x] `eval/compounding.py`: LIVE walk-forward loop — re-curates each week as-of, shows the belief
      lifecycle (L03 retired ~06-23, L08 trap retired ~08-04) + rising cum. gap → 92.90%.
      Live (re-curated weekly) ≈ hindsight (93.03%): the system would have won in real time.
- [x] `eval/validate.py`: per-belief ablation (L11 worth +€4,528; rest ~€0 atop the trim),
      sensitivity (36 configs, 12% spread, ALL beat B2), noise floor (engine €16,346 ≈ oracle
      2-regime floor €16,345 → at the irreducible limit; residual is day-to-day noise).
- [x] `eval/show_graph.py` + `BeliefGraph.render_text(as_of=)`: honest text graph snapshots;
      exports `submissions/belief_graph.json` (the Neo4j/frontend payload).
- [x] as-of curation made rigorous (supersession + render respect what was known). 34 tests pass.

## Phase 6 — Application (backend API + frontend)  [~]
Plan: docs/APP_PLAN.md. Stack: FastAPI + React/Vite/TS + React Flow, monorepo (api/ + web/).
- [x] **6a Backend API** — `api/` (state.py precompute+cache, schemas.py, main.py). 8 endpoints,
      CORS, `/docs`. `Engine.explain()` powers the trace. 11 API tests; live smoke-tested. 45 total pass.
- [x] **6b Frontend scaffold** — `web/` Vite+React 18+TS, Paretos token theme (docs/DESIGN_SYSTEM.md),
      typed API client + TanStack Query hooks (all 11 endpoints), router + segmented mode toggle,
      AppHeader, primitives (Button/Card/KpiTile/Badge), live SummaryBand. Build + typecheck green;
      proxied `/api/summary` renders real 93.03% / €218k end-to-end. `scripts/run_web.sh` runs both.
- [ ] 6c Normal mode — "Planner's Desk".
- [ ] 6d Advanced mode — "Knowledge Cockpit" (React Flow graph + trace + timeline + validation).
- [ ] 6e Polish + demo script.

## Phase 7 — Submission & story  [ ]
- [ ] Final submission.csv + a short write-up of the compounding narrative (the judging story).
