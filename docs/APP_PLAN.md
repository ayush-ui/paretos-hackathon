# APP_PLAN.md — Realising the application (Phase 6)

> Locked decisions (2026-06-27): **Backend** = FastAPI (Python, wraps `src/`). **Frontend** =
> React + Vite + TypeScript. **Graph viz** = React Flow. **Layout** = monorepo (`api/` + `web/`
> alongside `src/`, `eval/`, `docs/`). Scope = hackathon core only, NO external data sources yet.

## 1. Architecture
Thin FastAPI layer over the existing engine. On startup it runs what we already built (load data →
build+curate graph → backtest → compounding loop → holdout plan → as-of graph snapshots) and caches
everything in an in-memory `AppState`. Endpoints serve from cache → instant, no per-request compute.
No database for the core; Neo4j stays an optional later enhancement. The JS SPA calls the API over
HTTP/JSON and renders two modes.

```
web/ (React+Vite+TS SPA)  ──HTTP/JSON──►  api/ (FastAPI)  ──imports──►  src/ engine (unchanged)
   ├─ Normal mode                            └─ AppState (precomputed cache)
   └─ Advanced mode
```

## 2. Backend API surface (one surface, both modes)
All under `/api`. Every response has a Pydantic schema → auto OpenAPI docs at `/docs`.

| Endpoint | Returns |
|---|---|
| `GET /api/summary` | baseline vs B2 vs engine cost, gap-closed %, € saved, cost breakdown |
| `GET /api/plan/current` | upcoming plan rows `{date, planned, recommended, saving, weekday}` |
| `GET /api/plan/{date}/trace` | step-by-step: recommend→k→regime→offset→trend→final (+actual/cost if known) |
| `GET /api/cycles` | decision weeks w/ per-cycle cost & gap-closed |
| `GET /api/graph?as_of=DATE` | belief graph snapshot: nodes (status/trust/window/evidence) + typed edges |
| `GET /api/beliefs/{id}` | one belief: claim, author, lifecycle, € contribution, evidence |
| `GET /api/compounding` | weekly belief-status timeline + cumulative gap-closed curve |
| `GET /api/validation` | ablation table, sensitivity sweep, noise floor |

`as_of` on `/api/graph` powers the **time-slider** (watch beliefs go active/retired over weeks).
CORS open to the Vite dev server. Health: `GET /api/health`.

## 3. Data contracts (key shapes — finalised as Pydantic models in api/schemas.py)
- **PlanRow**: `{date, weekday, planned, recommended, saving_eur, actual?, cost?}`
- **TraceStep / Trace**: `{date, recommended, regime_boundary, k, level, offset, trend_adj, planned,
  actual?, our_cost?, baseline_cost?, reason_text}`
- **BeliefNode**: `{id, kind, status, scope, activities, valid_from, valid_to, trust, author, note,
  contribution_eur, evidence[]}`
- **GraphEdge**: `{src, dst, kind}`  (kind ∈ supersedes|contradicts|reaffirms|refines)
- **CompoundingPoint**: `{decision_date, statuses{id:status}, cycle_cost, cum_gap_pct}`

## 4. Normal mode — "The Planner's Desk"
Hide ALL internals (beliefs, k, regimes). Components:
- **This week's plan** — per day, big "staff N", optimiser number shown faded.
- **One plain-English reason** per week + **confidence badge** (low/med/high).
- **Accept / adjust** per day (override logged; future-friendly).
- **Track record** — one line + small trend ("last 8 weeks: €X vs €Y doing nothing, 92% better").
Powered by `/api/plan/current`, `/api/plan/{date}/trace` (reason only), `/api/summary`.

## 5. Advanced mode — "The Knowledge Cockpit"
- **Interactive belief graph** (React Flow) — nodes colored by status, typed edges; click → detail
  panel; **time-slider** drives `as_of`. Powered by `/api/graph`, `/api/beliefs/{id}`.
- **Decision trace** — pick a day → full step-by-step. `/api/plan/{date}/trace`.
- **Compounding timeline** — lifecycle grid + cumulative gap curve. `/api/compounding`.
- **Validation panel** — baseline/B2/engine, ablation, sensitivity, noise floor. `/api/validation`.

## 6. Build order
1. **6a Backend** — `api/`: app, AppState precompute, schemas, endpoints, CORS, endpoint tests. Prove via `/docs`.
2. **6b Frontend scaffold** — `web/`: Vite+React+TS, API client (typed), router, mode toggle.
3. **6c Normal mode** screens.
4. **6d Advanced mode** (graph + trace + timeline + validation).
5. **6e Polish + demo script.**

## 6b. Frontend execution plan (detailed — current work)
Design language = **docs/DESIGN_SYSTEM.md** (exact Paretos tokens; Inter substitute for AeonikPro;
brand-faithful dashboard). Stack confirmed: **Vite + React 18 + TS**, **TanStack Query** (server
cache), **React Router**, **Recharts** (line/area), **React Flow** (belief graph), **lucide-react**
(icons), **@fontsource-variable/inter**. No CSS framework — plain CSS Modules over the token vars.

**Directory layout**
```
web/
  index.html
  vite.config.ts            # dev proxy /api → :8000
  package.json tsconfig*.json
  src/
    main.tsx  App.tsx  router.tsx
    theme/    tokens.css  theme.ts  global.css
    api/      client.ts (fetch wrapper) types.ts (mirrors api/schemas.py) hooks.ts (Query hooks)
    components/  Button Card KpiTile Chip Badge Table ModeToggle AppHeader Stat ...
    modes/
      normal/   PlannersDesk.tsx  WeekStrip DayCard ReasonCard TrackRecord
      advanced/ KnowledgeCockpit.tsx  BeliefGraph TimeSlider DecisionTrace CompoundingTimeline ValidationPanel
    pages/    Landing.tsx (mode picker, Paretos hero)
```

**Build sub-steps (in order, each independently runnable):**
1. **Scaffold + theme** — Vite app, `tokens.css` (§3 vars), `global.css` (reset, font, base type),
   `theme.ts` (chart colour map), Inter font. Acceptance: blank app boots on `:5173` with brand bg/font.
2. **API layer** — `types.ts` (hand-mirrored from the 11 endpoints, verified against live JSON),
   `client.ts` (typed `get`/`post`, base URL via env, error handling), `hooks.ts` (one `useX` per
   endpoint via TanStack Query). Acceptance: a throwaway probe logs real `/api/summary`.
3. **Primitives** — Button (3 variants), Card, KpiTile, Chip, Badge (confidence/status), Table,
   ModeToggle, AppHeader. Storybook-free; a `/kitchen-sink` dev route renders them all.
4. **App shell** — Router with `/` (Landing), `/normal`, `/advanced`; AppHeader with logo wordmark +
   segmented mode toggle; KPI summary band fed by `useSummary()`. **End-to-end proof for 6b.**
5. *(6c/6d handled in their own phases — scaffolded as routed stubs now.)*

**Conventions:** components read CSS vars only (no hex literals); numbers formatted via one
`format.ts` (€ + person-days, tabular-nums); all server reads go through hooks (no raw fetch in
components); holdout rows render with an `is_holdout` "forecast" treatment and never show actual/cost.

**Dev runtime:** API `uvicorn api.main:app --port 8000`; web `npm run dev` (proxy forwards `/api`).
`scripts/run_web.sh` to start both. CORS already allows `:5173`.

## 7. Conventions / notes
- Engine stays the source of truth; API is read-only over precomputed state (override endpoint is
  the only future write).
- Keep response schemas stable; version under `/api` if they change.
- `submissions/submission.csv` + `submissions/belief_graph.json` remain the canonical artifacts.
- Anti-reward-hacking still applies: the API must never expose or depend on holdout actuals.
