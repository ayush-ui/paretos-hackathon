# Backend API

Read-only FastAPI surface over the compounding staffing engine. Serves both frontend modes.

## Run
```bash
./scripts/setup.sh        # pip install -r requirements.txt (once)
./scripts/run_api.sh      # start the server (reads ANTHROPIC_API_KEY from .env)
./scripts/test_api.sh     # in a second terminal: smoke-test every endpoint
```
Or manually: `uvicorn api.main:app --reload --port 8000`.
- Interactive docs / live contract: http://localhost:8000/docs
- Health: http://localhost:8000/api/health
- The API auto-loads `.env` (via python-dotenv). `GET /api/llm/status` shows whether the LLM layer
  is active. Without a key, `/explain` and `/ask` fall back to the deterministic template.

First request to `/api/compounding` and `/api/validation` is slow (they run the live walk-forward
loop / sweep once, then cache). All other endpoints are instant.

## Endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/summary` | headline costs + gap-closed + breakdown |
| GET | `/api/cycles` | per-week engine vs baseline cost/gap |
| GET | `/api/plan/current` | the October holdout plan (20 day-rows) |
| GET | `/api/plan/{date}/trace` | step-by-step "why this number" (+ outcome on training days) |
| GET | `/api/graph?as_of=DATE` | belief-graph snapshot (nodes + typed edges) |
| GET | `/api/beliefs/{id}` | one belief in depth |
| GET | `/api/compounding` | weekly belief-status timeline + cumulative gap curve |
| GET | `/api/validation` | ablation + sensitivity + noise floor |

CORS is open to the Vite dev server (`http://localhost:5173`). The API never exposes holdout
actuals: holdout trace rows carry `is_holdout=true` and omit `actual`/cost fields.
