# PROGRESS.md — Live status (update every working session)

**Project:** Compounding staffing-decision engine for the Helios warehouse hackathon.
**Goal:** Beat the optimiser baseline on held-out October weeks via a self-curating belief +
adjustment loop, then visualise it. Scored in € on daily operative person-day total.

## Current phase: 7 — MERGE (two-team synthesis). See docs/MERGE_PLAN.md for the full checklist + status.

### Phase 7 — merge cycle 1 (DONE, tested: 61 tests pass; scored numbers byte-identical)
- Head-to-head settled on one cost fn: OUR engine wins train (93.03% vs 88.3%) AND out-of-sample
  (Sep frozen: 95.0% vs teammate 86.9%, flat-17% 91.9%). Edge holds OOS → keep our numeric engine.
- **OOS freeze-and-predict harness** added (`eval/oos.py`) — teammate's protocol, our cost fn; the
  honest October dress-rehearsal. Golden baselines pinned in `tests/test_oos.py` (train 93.03/OOS 95.0).
- **LLM-first belief extraction + deterministic fallback, cached + reviewed** (`src/extract.py`,
  `scripts/extract_beliefs.py`, `state/belief_extractions.json`): Claude reads each note's prose in
  date order w/ prior beliefs as context → richer claim + contradicts/supersedes (caught L09⊣L08,
  L11/L12▸L03, L10▸L02). VALIDATION GATE: LLM-first scored 91.10% train / 83.3% OOS — *worse* than
  the hint path → hint stays the SCORED default; LLM extraction ships as the richer KNOWLEDGE layer
  (`build_graph(use_llm=True)`), not the numeric default. `src/beliefs.py` refactored to a single
  per-entry builder (`belief_from_entry`) shared by both paths.
- **Robustness fix**: engine/curation now treat kind `trend` ≡ `note` (an LLM saying 'trend' can't
  silently disable the October trend lead). Additive; hint path unchanged.
- **DB decision**: local files + `state/` folder now; PostgreSQL/Neon for mutable state → TECH_DEBT.
- NEXT (pending, see MERGE_PLAN): protective-lean A/B, provenance KG ontology
  + cockpit views, shadow-trust trajectory, state/ persistence adapter.

### Phase 7 — merge cycle 2 (IN PROGRESS, 64 tests pass; submission byte-identical)
- **[Step 1 DONE] Synthetic stress-test** (`eval/synthetic_stress.py` + `tests/test_synthetic.py`):
  re-implemented the teammate's regime-world generator on OUR data + `src.cost` (numpy only for seeded
  noise; nothing imported from the read-only teammate folder). Worlds: autumn ramp / strong ramp / heat
  drag / flu absence / pick-by-light, every knob grounded in the measured ratio + planner notes (heat/flu
  windows clearly labelled what-if). Fair comparator = the **no-knowledge ablation engine** (our engine
  minus belief graph + trend lead). Engine BEATS the ablation on autumn ramp (91.5/90.6%), strong ramp
  (56.3/54.7%) and pick-by-light (88.5/87.6%); honestly neutral/worse on the unseen heat/flu shocks.
  SYNTHETIC evidence only — the real-data ablation stays primary.
- **[Step 2 DONE — NEGATIVE RESULT] Protective October lean A/B** (`eval/protective_ab.py`): added two
  opt-in, default-off engine levers (`predict.Engine.k_window`, `.auto_offset`; the latter is a ported
  newsvendor best_offset grid-search). Gate = ≥93% train AND ≥95% OOS, or strict OOS gain w/o train
  regression. No variant cleared it (auto_offset 92.70/95.4%; recent-45d+auto 92.68/95.6% & 14/22 und —
  most protective but train-regressing). Kept the DEFAULT scored path; submission byte-identical. Levers
  remain available as an opt-in protective run. Tests in test_engine (defaults-off reproduce locked;
  levers live; A/B concludes no-adoption).
- **[Step 3 DONE] Provenance KG ontology** (`src/provenance.py`): in-process typed graph (no Neo4j/
  networkx) on top of the belief graph — Source|Belief|Decision|Outcome nodes + SOURCED_FROM/INFORMED/
  CONSIDERED/RESULTED_IN/UPDATED/PRECEDED/CONTRADICTS edges. Built WALK-FORWARD (each decision curated
  at its own Monday as_of; no node sees a future actual). Trace: plan→belief→note→€ outcome→trust
  update→next week. API: `GET /api/provenance?as_of=`, `GET /api/provenance/{week}/trace` (cached in
  AppState; as_of filters in-memory). Tests: tests/test_provenance.py (8).
- **[Step 4 DONE] Shadow-trust EWMA trajectory** (`src/trust_trajectory.py`): walk-forward per-belief
  trust curve, `trust=0.6*old+0.4*helped` where helped = measured weekly marginal € (retire→replan→
  compare). Pure observability; curation untouched. L08 trap decays 0.50→0.01; L03 peaks 0.70→0.00.
  API: `GET /api/trust` (cached). Tests: tests/test_trust.py (5).
- **[Step 5 DONE] Persistence adapter** (`src/persistence.py`): `Persistence` ABC + `FileStore` (atomic
  JSON under state/). `get_persistence()` = one-line swap to Postgres/Neon later (FileStore = offline
  fallback). NoteStore/AbsenceStore persist through it (DI-friendly); AppState dumps a graph snapshot at
  boot. Runtime blobs gitignored. Tests: tests/test_persistence.py (6). **86 tests pass; submission
  byte-identical; OOS-Sep 95.0% unchanged.**
- **[Step 6 DONE] Cockpit views** (`web/src/modes/advanced/`): three new Knowledge-cockpit tabs —
  Provenance (React Flow Source→Belief→Decision→Outcome, click-to-trace), Trust over time (Recharts
  EWMA per belief; L08 trap decays visibly), Robustness (engine vs ablation across synthetic regime
  worlds, badged SYNTHETIC). New endpoints: `/api/provenance(/{week}/trace)`, `/api/trust`,
  `/api/synthetic`; typed hooks added. `npm run build` (tsc -b + vite) green.

### Phase 7 — cleanup + dockerization (post-merge)
- **Workspace tidy:** deleted the read-only `team_mate _code/` folder (model already ported, nothing
  imports it), all `__pycache__`, `.pytest_cache`, `web/dist`, and `.DS_Store`. Kept the
  provenance/trust/validation BACKEND + tests (user chose to keep) even though their UI tabs were removed.
- **Dockerized the full app** (`Dockerfile` for API/bot, `web/Dockerfile` multi-stage → nginx serving
  the built SPA and proxying `/api` → api:8000, `docker-compose.yml`, `.dockerignore` ×2, `README.md`).
  One-line start: **`docker compose up --build`** → http://localhost:5173 (API also on :8000). Bot is an
  optional `--profile bot` service. Added `numpy` to requirements (the live /api/synthetic endpoint needs
  it). VERIFIED: both containers build + run, api healthy, summary 93.03%, staffing/synthetic respond
  through the nginx proxy.

### Phase 7 — cockpit UX rework (post-merge, on user feedback)
- Knowledge graph is now the HERO of the Knowledge tab (improved `BeliefGraph`: status lanes —
  active/candidate/retired rows, time left→right, rich node cards w/ trust bar + €, clearer edges +
  lane legend). Dropped the separate "Relationships" tab (merged into Knowledge).
- New time-series charts: **Cumulative cost (€)** added to the Compounding tab (plan vs baseline,
  accrued weekly); new **Staffing** tab (`StaffingPanel` + `GET /api/staffing`: per-week operative
  person-days plan vs optimiser vs actual, holdout marked, actuals omitted there). Trust-over-time
  chart kept as its own tab.
- Removed the Provenance graph tab + `ProvenancePanel` (too dense per user). The `/api/provenance`
  backend + tests remain (valuable, still green) — only the UI was retired.
- Added a reusable **Loader** (`components/Loader.tsx`: spinner + `PanelLoader`) and applied it across
  all loading states (Knowledge, Staffing, Compounding, Trust, Robustness, Validation, BeliefDetail,
  Planner's Desk). `npm run build` green. New test: staffing endpoint in test_api.

### Phase 7 — merge cycle 2 COMPLETE: all 6 pending MERGE_PLAN items shipped or honestly closed.
- Adopted: synthetic stress eval (#1), provenance KG (#3), shadow-trust trajectory (#4), persistence
  adapter (#5), cockpit views (#6). Negative result (not adopted, documented): protective lean (#2).
- Gates held throughout: scored default unchanged, submission byte-identical, OOS-Sep 95.0%, train
  93.03%. New capabilities each covered by tests.

### Phase 6 recap: app build. Steps 0/1/2/3 DONE.

### Planner-note capture (DONE) — human-in-the-loop knowledge
- Planner writes a free-text observation → AI (note_parser) structures it → preview "here's how I
  understood it" → confirm → added to the graph as a CANDIDATE belief (id P01..), authored by her.
- Backend: api/notes.py (NoteStore JSON persist + interpret/build_belief), AppState.note_preview/
  note_commit/note_delete + _load_planner_notes at boot; graph_snapshot.cache_clear on mutate.
  Endpoints: POST /api/notes/preview, POST /api/notes, DELETE /api/notes/{id}.
- Verified: committed note appears in graph (16 nodes) and the locked Oct plan is UNCHANGED (candidate,
  valid_from=today, doesn't fire on the current plan — captured for future curation, honest/safe).
- Frontend: components/NoteComposer.tsx (write → "Review with AI" → interpretation card → "Add to
  knowledge"), placed in Planner's Desk (compact) + Knowledge tab. Graph query invalidated on commit.
- Knowledge cockpit legibility reworked: KnowledgeIntro explainer + readable BeliefList (notes grouped
  active/candidate/retired, plain English) as default "Knowledge" tab; graph fixed (human labels=scope+
  author, lane layout, framing) and moved to "Relationships" tab.

### Step 3 — Advanced "Knowledge Cockpit" (DONE)
- `modes/advanced/` rebuilt with 4 tabs: Belief graph | Decision trace | Compounding | Validation.
- BeliefGraph (React Flow): deterministic time-layout (x=valid_from, y=stack), nodes colored by status
  (active=violet/candidate=turquoise/retired=grey), edges by kind (supersedes=violet, contradicts=red
  dashed, reaffirms=green), click→BeliefDetail drawer (€ contribution, evidence, lifecycle). TimeSlider
  scrubs as_of over the 20 decision weeks (verified: 0→7→13→15 nodes as knowledge accumulates).
- DecisionTrace: pick a day → 7-step derivation (optimiser→regime→k→level→offset→trend→final) + outcome
  (holdout shows 'forecast/no peeking'; training days show actual + €saved). CompoundingTimeline: cum
  gap-closed area chart + belief-lifecycle status grid. ValidationPanel: ablation bar + sensitivity +
  noise floor. All wired to existing endpoints (/graph?as_of, /beliefs/{id}, /compounding, /validation,
  /plan/{date}/trace). Typecheck+build green; data verified through the Vite proxy.
- Fill-the-gap bug fixed earlier: optimistic update in useResolveAbsence → instant card flip.

### Step 2 — Discord absence loop (DONE, live-tested to the API boundary)
- Config in .env (gitignored): DISCORD_BOT_TOKEN/GUILD_ID/ABSENCE_CHANNEL_ID. Bot = "Pareto_Bot" in
  "Paretos" server; connection validated. **Regenerate token after the event.**
- Backend: `api/absences.py` (AbsenceStore, in-memory + JSON persist), coverage+€risk via src/cost.py
  (1 short=€41; 3 short=€724 SLA breach). Wired into `current_plan` (confirmed/coverage/short_by/
  sla_risk). Endpoints: POST/GET /api/absences, POST /api/absences/{id}/resolve, DELETE /api/absences,
  GET /api/plan/dates. CORS now allows POST/DELETE.
- Parser: `src/absence_parse.py` — free text → exact plan date + reason via the LLM choke point
  (llm.parse), deterministic weekday/ISO fallback. Verified: "Tuesday, sick" → 2026-10-06.
- Bot: `bot/main.py` (discord.py, MESSAGE CONTENT intent) → parse → POST → embed reply. `scripts/run_bot.sh`.
- Frontend: live polling (4s) on plan+absences; AbsenceAlert banner; DayCard turns amber/red when short,
  shows absent workers + €risk + Fill/Accept resolve buttons (useResolveAbsence). Build+typecheck green.
- Run all: API `uvicorn api.main:app --port 8000`; bot `scripts/run_bot.sh`; web `cd web && npm run dev`.
- REMAINING: the human-in-Discord test (type in #general → watch the app go red). Bot logic proven via
  simulation (parse→POST→impact) + bot is connected & listening.

### Product reframe (docs/PRODUCT_PLAN.md) — make it usable for a shift planner
- Problem: UI showed optimisation internals (person-days, trim %, gap) a planner can't act on.
- 3 workstreams: A) legible Normal "Planner's desk", B) Discord absence loop (free-text+LLM parse →
  /api/absences → Resolve flow), C) Advanced "Knowledge cockpit" (graph + trace + curation).
- Sequence: A (done) → B (needs paretos: bot token, guild/channel IDs, worker↔discord map, Message
  Content intent) → C → wire Discord patterns into candidate beliefs (compounding climax).

### Step 0+1 — translation layer + legible Planner's desk (DONE)
- Decision: 1 person-day = 1 person/shift → headcount = round(person-days). Roster synthesised on top
  of real numbers (dataset has no named workers) — labelled in-app.
- Backend: PlanRow now carries target/optimiser/confirmed headcount, coverage, **honest confidence**
  (from regime-ratio CV, capped at "medium" for the October forecast), reason_short. (api/state.py)
- Frontend: PlannersDesk rebuilt as day-cards ("Staff N people", optimiser faded, CoverageBar,
  confidence badge, plain reason, "Why this number" → /explain w/ LLM), + AboutPanel explainer,
  TrackRecord strip (/summary), WeekChart (Recharts optimiser-vs-plan), week picker. Build+typecheck
  green; verified live (explain uses LLM). NOTE: PlanRow schema changed → update tests if they pin it.

### Phase 6b — Frontend scaffold (DONE; re-skinned to the official Cockpit system)
- **IMPORTANT correction:** paretos supplied their official **Cockpit Design System** prompt, which
  SUPERSEDES the tokens we first reverse-engineered from their marketing site. Marketing ≠ product.
  Cockpit rules now in `docs/DESIGN_SYSTEM.md`: **primary action = BLACK** (not mint), **sentence
  case** (no all-caps), **7px** radius (not 16px), **1px #CCC** borders (hover → #666), **violet
  #5F26E0** = selection/focus/links/AI, magenta→amber **brand gradient used sparingly**, borders not
  shadows, **sidebar+topbar cockpit shell** full-width w/ 40px gutters (no max-width cap). Aeonik Pro
  → Inter substitute (license-safe, single-swap var); Consolas mono for tabular values.
- Re-skinned all primitives + shell to Cockpit: Topbar (60px, gradient logo square) + Sidebar (180px,
  violet selection, Lucide@strokeWidth1) replace the old marketing header/mode-toggle.
- `web/` Vite+React 18+TS: token theme (tokens.css/global.css/theme.ts), typed API client +
  TanStack Query hooks for all 11 endpoints, router with `/` `/normal` `/advanced`, segmented
  ModeToggle, AppHeader, primitives (Button/Card/KpiTile/Badge/SummaryBand).
- Normal/Advanced routed stubs render REAL data now (plan rows, beliefs, ablation) — rich screens
  are 6c/6d. `npm run build` + typecheck green; Vite proxies `/api` → :8000 (proven 93.03%/€218k).
- Run both: `scripts/run_web.sh`. Decisions: Inter (license-safe, swappable), brand-faithful dashboard.

### LLM layer (DONE, optional, off by default)
- Provider Claude `claude-opus-4-8`. `src/llm.py` (choke point), `src/note_parser.py` (A: free-text
  note → candidate hypothesis + one-off-vs-pattern flag), `src/narrator.py` (B: explain/ask over
  verified trace). API: `GET /api/llm/status`, `GET /api/plan/{date}/explain`, `POST /api/ask`.
- **LLM never touches numbers** — proposes candidates (still pass curation) + narrates verified facts.
  Engine cost identical with LLM off (pinned by test). Graceful fallback w/o ANTHROPIC_API_KEY.
- Activate: `pip install -r requirements.txt`; `export ANTHROPIC_API_KEY=...`. Calls are on-demand
  only (explain/ask), not during planning/startup. Docs: docs/LLM_INTEGRATION.md. **52 tests pass.**

### Phase 6a — Backend API (DONE)
- `api/` FastAPI: `state.py` (AppState precompute+lazy cache), `schemas.py` (Pydantic), `main.py`.
- 8 endpoints: summary, cycles, plan/current, plan/{date}/trace, graph(?as_of), beliefs/{id},
  compounding, validation. CORS for Vite. Interactive contract at `/docs`.
- `Engine.explain()` added to src/predict.py → powers the trace ("why this number").
- Run: `uvicorn api.main:app --reload --port 8000`. Deps: `requirements.txt` (fastapi/uvicorn/httpx).
- Anti-leakage enforced in API: holdout trace rows carry is_holdout=true, omit actual/cost.
- **45 tests pass** (11 new API tests + live curl smoke test verified).
- Plan locked in docs/APP_PLAN.md: React+Vite+TS, React Flow, monorepo api/ + web/.



### Phase 5 validation (all honest / walk-forward)
- LIVE loop (`eval/compounding.py`): re-curates weekly using only data known then → **92.90%**,
  ≈ hindsight 93.03% (no overfit gap). Lifecycle visible: L03 retired ~2026-06-23, L08 trap retired
  ~2026-08-04 once late-summer weeks are observed.
- ABLATION (`eval/validate.py`): L11 (pick-by-light regime belief) worth **+€4,528**; all other
  beliefs ~€0 on top of the global trim (double-counting). Graph value = 1 regime belief + governance.
- SENSITIVITY: 36 hyperparameter configs, 12% cost spread, **all 36 beat the B2 bar** (not overfit).
- NOISE FLOOR: engine €16,346 ≈ oracle 2-regime floor €16,345 → at the irreducible limit on training.
- `eval/show_graph.py`: text belief-graph + `submissions/belief_graph.json` export. **34 tests pass.**
- HOLDOUT RISK: October is a rising regime; training is near-saturated, so the holdout edge rides on
  the trend term + regime trim generalising. Do NOT tune to a holdout proxy.



### Headline result (walk-forward on 98 training days)
| Strategy | Cost | Gap closed |
|---|---|---|
| B0 baseline | €234,600 | 0.0% |
| B1 flat −17% | €19,656 | 91.62% |
| **B2 EW ratio (the bar)** | €21,043 | 91.03% |
| **ENGINE (belief-led)** | **€16,346** | **93.03%** |
| engine w/o graph (ablation) | €19,537 | 91.67% |

→ Engine beats the B2 bar by ~2pp; the **belief graph is worth +1.36pp / ~€3.2k** (ablation).
Mechanism: curation auto-retires the L08 trap (saves €53.9k vs naive apply-all) and the
pick-by-light note (L11, survives) supplies the **regime boundary 2026-08-25** that segments the
adaptive trim. Submission for the 4 October holdout weeks → `submissions/submission.csv` (20 days).
28 tests pass (incl. leakage guard + regression guard that the engine beats B2).

### Done
- Explored dataset; verified key numbers (baseline €234.6k, ~0.84 need/rec ratio, flat-17%≈92% gap).
- Confirmed the **total-only actuals** constraint (no per-activity ground truth).
- Empirically: pick-by-light ratio drop 0.845→0.82 (08-24); L09 > L08; autumn ramp real.
- Authored docs: DATA_REFERENCE, DECISION_LOG_ANALYSIS, ARCHITECTURE, ROADMAP, ANTI_REWARD_HACKING.
- **Phase 1 DONE**: `src/cost.py` (exact day_cost), `src/data.py` (zero-dep loaders + raw German-
  decimal rec parser), `eval/backtest.py` (walk-forward harness w/ enforced info horizon).
- **Tests**: 18 passing (cost asymmetry + 2.0 SLA boundary; raw-parser == clean export).
- **Anchors reproduced exactly**: B0 €234,600 (0%), B1 flat-17% €19,656 (91.6%).
- **Phase 2 baseline ladder locked** — the bar to beat is **B2 EW-ratio = 91.0%** (hl14, walk-fwd).

### Key Phase-1 finding (drives Phase 4)
Best *global constant* trim is k=0.83 → only 91.6% (barely below mean ratio 0.838). The global
lever is nearly exhausted: the remaining ~€20k / ~9pp must come from **per-day prediction**
(regime change, weekday, trend) + **asymmetric-loss tail management**, not a better single number.

### Next up (immediate)
1. Phase 6b: scaffold `web/` (Vite + React + TS), typed API client against the 8 endpoints,
   router + Normal/Advanced mode toggle.
2. Phase 6c Normal "Planner's Desk", 6d Advanced "Knowledge Cockpit" (React Flow graph w/ as_of
   time-slider, decision trace, compounding timeline, validation panel).
3. Optional later: Neo4j exporter (`src/graph_store.py`) reading NEO4J_* env vars; payload is
   `submissions/belief_graph.json` (or GET /api/graph).

### Open questions for the user
- Stack confirmation (Python engine + which frontend) — see ARCHITECTURE §7.
- Heavy graph DB vs lightweight in-process graph (recommend lightweight).
- `git init` now? (not yet a repo).

### Key facts to remember
- Submission format: `date,planned_operative_person_days` for the 4 holdout weeks.
- Everything walk-forward; beat **B2 (EW trailing ratio)**, not just baseline.
- Doc index lives in `/CLAUDE.md`.
