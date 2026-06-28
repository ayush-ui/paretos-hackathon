# MERGE_PLAN.md — merging the two team approaches into one optimised solution

> Decision basis: head-to-head analysis (see `memory` + PROGRESS). Governing principle:
> **keep our engine as the spine (it wins on the real metric), graft in the teammate's superior
> *ideas* — gated behind validation so nothing regresses below the proven baselines.**

## Golden baselines (the regression gates — never silently drop below these)
Verified 2026-06-28 on one cost function, deterministic **hint** (scored) path:

| Metric | Value | Pinned by |
|---|---|---|
| Training walk-forward gap | **93.03%** (€16,346), beats B2 (91.03%) | `tests/test_oos.py`, `tests/test_engine.py` |
| OOS September (frozen at Aug 31) | **95.0%** (€3,032), MAE 1.31 | `tests/test_oos.py` |
| Ablation: belief graph worth | +1.36pp / ~€3.2k | `tests/test_engine.py` |
| October submission | 20 day-plans, ~16.8% trim | `eval/submit.py` |

Head-to-head context: teammate backbone 88.3% (train) / 86.9% (OOS-Sep); their belief loop adds
~€0 on real data. **Our edge holds out-of-sample**, so we keep our numeric engine.

---

## Done this cycle (implemented + tested, app fully working)

- [x] **Lock golden baselines** as regression tests (`tests/test_oos.py`) — training 93.03%, OOS-Sep 95.0%.
- [x] **Formalise the OOS freeze-and-predict harness** (`eval/oos.py`) — the teammate's protocol, our
      cost function. The honest dress rehearsal for the October holdout. *Rationale: a stricter test
      than per-cycle walk-forward (no mid-block relearn); it is how we choose any holdout-lean change.*
- [x] **LLM-first belief extraction with deterministic fallback, cached + reviewed** (`src/extract.py`,
      `scripts/extract_beliefs.py`, `state/belief_extractions.json`). Claude reads each note's prose in
      date order with prior beliefs as context, emits a richer `claimed_effect` + `contradicts`/
      `supersedes`. *Rationale: reads the signal in the words (negation, disputes) the pre-baked hint
      flattens; more on-thesis. Cache = frozen, reviewed, deterministic input; fallback = the hint, so
      the scored path needs no key and reproduces the locked numbers.*
  - **Validation outcome (the gate working):** LLM-first scored **91.10% train / 83.3% OOS-Sep** —
    *worse* than the hint path (it retires L08 entirely and leans up via L09). So per the gate, the
    **hint path remains the scored default**; the LLM extraction ships as the **richer knowledge/
    relationship layer** (it correctly caught L09⊣L08, L11/L12▸L03, L10▸L02), available via
    `build_graph(use_llm=True)`, *not* as the numeric default.
- [x] **kind `trend`≡`note` robustness fix** (`src/predict.py`, `src/curate.py`) — the engine now
      recognises both labels for trend/parking, so an LLM that says `trend` instead of `note` can't
      silently disable the October trend lead. *Additive; hint path unchanged (verified 93.03%).*
- [x] **Verify L15 (autumn-ramp, captured 2026-09-29) legitimately informs October** — it does in our
      code (end-state graph + `_trend_active`); pinned by `tests/test_oos.py`. *This was a teammate-code
      bug (their cutoff dropped it), not ours.*
- [x] **DB decision** → local files + `state/` folder now; PostgreSQL/Neon for mutable state later
      (logged in `TECH_DEBT.md`, behind a one-adapter swap).

## Pending (next executable steps — each still gated by the baselines above)

- [x] **Port the synthetic stress-test generator** (teammate `synthetic.py` → new `eval/synthetic_stress.py`),
      run *our* engine through the regime worlds (autumn ramp / strong ramp / heat / flu / pick-by-light).
      *Rationale: demonstrates robustness to regimes the single real October can't show — jury material.
      Labelled SYNTHETIC; the real-data ablation stays primary.* **Done 2026-06-28:** re-implemented the
      generator on our data + `src.cost` (no import from the read-only teammate folder; numpy only for
      seeded noise). The fair "naive" comparator is the **no-knowledge ablation engine** (our engine minus
      belief graph + trend lead) — the same comparator the real-data ablation uses. Result: the engine
      **beats the ablation on autumn ramp (91.5 vs 90.6%), strong ramp (56.3 vs 54.7%), and pick-by-light
      (88.5 vs 87.6%)** — the learnable regimes; honestly neutral/slightly worse on the pure unseen shocks
      (heat/flu) it has no belief for. Test `tests/test_synthetic.py` pins runs+determinism and the ramp win.
- [x] **A/B a protective October lean** (recent-N-day k and/or data-driven `best_offset`) via OOS-Sep.
      *Rationale: our Sep plan understaffs 16/22 days (within tolerance now, but close to the €600 cliff
      if October ramps higher). Adopt only if it holds OOS.* **Done 2026-06-28 — NEGATIVE RESULT, not
      adopted.** Both levers added to `predict.Engine` as **opt-in, default-off** options (`k_window`,
      `auto_offset`); A/B reproducible via `eval/protective_ab.py`. Gate = ≥93% train AND ≥95% OOS, or
      strictly-improves-OOS without train regression. Results: `recent-45d k` 93.00/94.7% (OOS worse),
      `auto_offset` 92.70/95.4% (improves OOS but regresses train below 93), `recent-45d+auto_offset`
      92.68/95.6% & only 14/22 understaffed (most protective, but train regression). **No variant clears
      the gate**, so the DEFAULT scored path is unchanged (submission byte-identical). The levers stay
      available for an opt-in protective run if October is feared to ramp hard; logged in TECH_DEBT.
- [x] **Provenance KG ontology** — add Decision / Outcome / Source nodes + INFORMED / RESULTED_IN /
      UPDATED / PRECEDED edges (teammate `kg.py` idea) on top of our belief graph; render in the existing
      React Flow. *Rationale: the biggest jury upgrade — trace a plan → belief → note → € outcome →
      trust update → next week. In-process, no Neo4j.* **Done 2026-06-28:** `src/provenance.py` — a
      plain in-process typed graph (no networkx/Neo4j) built WALK-FORWARD (each Decision curated at its
      own decision-Monday `as_of`, so no node depends on a future actual). Ontology: Source | Belief |
      Decision | Outcome; edges SOURCED_FROM / INFORMED / CONSIDERED / RESULTED_IN / UPDATED / PRECEDED /
      CONTRADICTS. Full graph = 3 sources, 15 beliefs, 24 decisions, 24 outcomes, 186 edges. INFORMED =
      beliefs that materially shaped the plan (regime boundary / active trend / firing structural);
      others eligible = CONSIDERED. Exposed via `GET /api/provenance?as_of=` and
      `GET /api/provenance/{week}/trace`; cached once in `AppState`, as_of views filter in-memory.
      Tests: `tests/test_provenance.py` (ontology, source-coverage, decision↔outcome 1:1, edge
      referential integrity, as_of honesty, trace chain, API wiring).
- [x] **Shadow-trust EWMA trajectory** alongside forward-pruning — a legible week-by-week trust curve.
      **Done 2026-06-28:** `src/trust_trajectory.py` — replays decisions walk-forward and, each week,
      measures whether a belief HELPED (retire it, re-plan that week with only data known then, compare
      € on the week's scored days), then smooths with `trust = 0.6·old + 0.4·helped`. Pure observability
      — curation/forward-pruning is untouched (still powers the ablation). The curve tells the story:
      L08 (the trap) decays 0.50→0.01 as it's retired; L03 peaks 0.70 then falls to 0.00 on supersession.
      API: `GET /api/trust` (cached). Tests: `tests/test_trust.py` (EWMA recurrence, bounds, L08 decay,
      walk-forward start, API). NOTE: this is a per-week single-belief marginal signal, so it can differ
      from the cumulative ablation €.
- [x] **`state/` persistence adapter** for graph snapshots + planner notes + absences (file now,
      Postgres/Neon later behind the same interface). **Done 2026-06-28:** `src/persistence.py` — a
      minimal `Persistence` ABC (`load/save/exists/delete` over namespaced collections) + a `FileStore`
      writing atomic JSON under `state/`. `get_persistence()` is the one-line swap point (select a
      `PostgresStore` when `DATABASE_URL` is set; FileStore stays the offline fallback). `NoteStore` and
      `AbsenceStore` refactored to persist THROUGH the adapter (constructor takes an optional backend for
      DI/tests); `AppState` writes a lightweight graph snapshot to `state/graph_snapshot.json` at boot.
      Runtime blobs gitignored; reviewed `belief_extractions.json` stays committed. Tests:
      `tests/test_persistence.py` (round-trip, overwrite/delete, corrupt-tolerance, store round-trip via
      injected backend).
- [x] **Cockpit views** for the provenance graph + trust-over-time curve + the synthetic robustness panel.
      **Done 2026-06-28:** three new Knowledge-cockpit tabs in `web/src/modes/advanced/` — **Provenance**
      (`ProvenancePanel.tsx`, React Flow: Source→Belief→Decision→Outcome lanes, click a decision to trace
      it back to the beliefs/notes that shaped it and forward to its € outcome), **Trust over time**
      (`TrustCurve.tsx`, Recharts EWMA lines per belief; L08 trap visibly decays), **Robustness**
      (`SyntheticPanel.tsx`, engine vs ablation across regime worlds, clearly badged SYNTHETIC). New
      typed hooks (`useProvenance/useProvenanceTrace/useTrust/useSynthetic`) over new endpoints
      (`/api/provenance`, `/api/provenance/{week}/trace`, `/api/trust`, `/api/synthetic`). `npm run build`
      (tsc -b + vite) green.

## Dropped (held out of the merge — with rationale)
- Teammate's multiplicative belief-nudge loop — €0 scoreable lift on the neutral harness.
- Mandatory-LLM (raise-without-key) — reproducibility + demo risk; we keep optional + fallback.
- SQLite/Postgres on the engine hot path — no scored benefit; local files suffice, DB is demo-risk.
- Neo4j — over-engineering for hundreds of nodes.
- Streamlit — our React cockpit supersedes it.
- "Weather-matching beliefs" / `--discover` — **not implemented in the teammate code** (synthetic-only
  knob / absent flag); do not build on them.

## How to operate
- Scored engine (default, deterministic): `curate.build_graph()` → hint path.
- LLM-first knowledge layer: `curate.build_graph(use_llm=True)` (reads the reviewed cache; no key
  needed once `state/belief_extractions.json` is committed and all notes are 'fresh').
- Regenerate the extraction cache: `python3 scripts/extract_beliefs.py` (needs `ANTHROPIC_API_KEY`),
  then **review** `state/belief_extractions.json` before committing.
- OOS dress rehearsal: `python3 eval/oos.py`. Full backtest + ablation: `python3 eval/submit.py`.
