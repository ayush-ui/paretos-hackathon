# TECH_DEBT.md — Known shortcuts, risks, and debts

Log anything taken as a shortcut, any assumption that needs revisiting, any risk. Date entries.

## Open
- (2026-06-27) No `SOLUTION/scoring.py` is present in the dataset — we replicate `day_cost` from
  cost_model.json + README §5. RISK: if facilitator scoring differs (rounding, clipping negatives,
  weekend handling), our backtest could diverge. ACTION: keep the cost fn in one place; if the real
  scorer surfaces, diff against it.
- (2026-06-27) Per-activity claims (L01–L15) can only be validated via the daily TOTAL + volumes —
  no per-activity actuals. Belief validation is therefore indirect/weaker for micro-rules; weight
  low-n conditional rules (L05, L07, L13) cautiously.
- (2026-06-27) Holdout has a public holiday (2026-10-03, but it's a Saturday — likely no working-day
  impact). Confirm the holdout planned days exclude weekends/holidays before scoring.
- (2026-06-28) **DB deferred — local-folder persistence for now.** DECISION: raw dataset stays in
  local files (std-lib loaders, source of truth); derived graph + provenance persist to a local
  `state/` folder (versioned JSON, rebuilt on data/logic change); mutable live state (planner notes,
  absences, trust history) stays JSON-on-disk. A hosted server DB is NOT needed for the engine and is
  a live-demo liability (network dependency). DEBT: migrate the *mutable-state* tier to PostgreSQL
  (Neon) post-hackathon for durability/multi-user — keep a local fallback so the engine runs offline.
  Engineer the persistence layer behind a small interface so the file→Postgres swap is one adapter.
  (Note: no MySQL anywhere; teammate's code used SQLite, ours used CSV — Postgres would be the target.)

## Workstream B — Discord absence loop (2026-06-28)
- **Synthesised roster.** Dataset has daily person-day TOTALS only (no named workers), so the roster
  (named people / who's on which day) is a PRODUCT layer: 1 person-day = 1 person/shift, an absence
  lowers confirmed by 1. The € risk of a shortfall IS real (uses src/cost.py asymmetric model), but the
  named-worker assignment is illustrative. Labelled in the UI ("About this plan") so it's not misleading.
  If real rosters surface, swap the synthetic pool in api/absences.py for actual assignments.
- **Absence store is in-memory + JSON** (api/_absences.json, gitignored). Fine for a single-process demo;
  not multi-worker safe. No auth on /api/absences (anyone on localhost can POST). Acceptable for the
  hackathon; gate before any real deployment.
- **Bot token was shared in chat** → regenerate after the event (Developer Portal → Bot → Reset Token).
- **'filled' resolution** assumes a standby can always be found; it doesn't model the standby's own cost
  beyond the avoided penalty. Good enough for the decision UX; refine if we add a real flex pool.

## Key architectural findings (Phase 3)
- (2026-06-27) **Double-counting:** applying per-activity %-cuts from beliefs AND a global residual
  ratio trim compounds (picking −27% × global −17% ≈ −40% → understaffs). At the TOTAL level the
  global-trim approach dominates structural decomposition (no per-activity actuals to anchor it).
  DECISION: the belief graph does NOT add per-activity cuts on top of the trim. Its roles are:
  (a) supply **regime boundaries** for a time-varying trim (the pick-by-light split → 91.6%→93.8%
  in-sample), (b) **govern/retire** bad knowledge (retiring L08 alone avoids €53.9k; naive
  apply-all loses €80k), (c) inform the **October trend** (autumn ramp underplanned by trailing k).
- (2026-06-27) Curation correctly auto-retires L08 (the trap) and expires stale picking beliefs via
  supersession — the compounding story holds. But promotion thresholds for small structural beliefs
  are moot given the double-counting decision above; they're kept for the knowledge-graph narrative,
  not the numeric path.

## Merge cycle 1 (2026-06-28)
- **LLM-first extraction underperforms the hint path on the score** (91.10% train / 83.3% OOS-Sep vs
  93.03% / 95.0%). Root causes seen: the LLM drops L08's `weeks` window-box (W30–W33) so L08 becomes
  open-ended, and it tags L09 as trend-up which leans the plan up (0/22 understaffed but costlier).
  DECISION: hint path is the scored default; LLM extraction is the knowledge/relationship layer only.
  ACTION (next): refine the extraction→belief mapping (preserve week-boxes; treat L09 as a non-numeric
  contradiction, not a trend) and re-validate; promote LLM-first to scored only if it holds ≥93%/95%.
- **`state/belief_extractions.json` is a reviewed artifact, not auto-trusted.** It must be re-reviewed
  after any `scripts/extract_beliefs.py --refresh`. No CI re-extraction (would be nondeterministic + cost).

## Merge cycle 2 (2026-06-28)
- **Synthetic stress-test depends on numpy** (`eval/synthetic_stress.py`) for seeded Gaussian noise.
  numpy is already an install dep; the SCORED engine path (src/, eval/backtest, eval/oos, eval/submit)
  stays std-lib-only, so this adds no dependency to the locked numbers — it's an eval-only tool. If we
  ever want zero-dep here, swap `np.random.default_rng` for `random.Random(seed).gauss`.
- **Protective October lean — NEGATIVE RESULT, not adopted (the gate working).** Added two opt-in,
  default-off engine levers (`predict.Engine(k_window=..., auto_offset=...)`) and A/B'd them in
  `eval/protective_ab.py`. None cleared the adoption gate (≥93% train AND ≥95% OOS-Sep, or strict OOS
  improvement without train regression): `auto_offset` lifts OOS to 95.4% but drops train to 92.70%;
  `recent-45d k + auto_offset` is the most protective (14/22 understaffed, OOS €2661 vs €3032) but also
  regresses train. DECISION: keep the DEFAULT scored path (submission byte-identical). DEBT/OPTION: if
  October is feared to ramp harder than September, an opt-in protective run is one kwarg away
  (`auto_offset=True`), but it trades ~0.3pp of the proven training edge for OOS protection — only flip
  it with a documented, holdout-honest reason and re-pinned baselines.
- **Synthetic worlds are what-if, not validated regimes.** The autumn-ramp/pick-by-light knobs are
  grounded in measured data + notes; the heat/flu drag windows are LABELLED simulation knobs. The engine
  is honestly weaker on the unseen heat/flu shocks (no belief for them) — this is reported, not hidden.
  Real-data ablation (eval/submit.py, eval/validate.py) remains the primary evidence; synthetic is
  robustness colour for the jury, never a scored claim.

## Resolved
- (none yet)
