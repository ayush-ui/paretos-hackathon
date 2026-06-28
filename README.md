# Helios — Compounding Staffing Cockpit

A self-curating decision engine for warehouse staffing. It learns the optimiser's weekly error,
curates that knowledge in a belief graph (promoting durable beliefs, retiring stale/harmful ones),
and emits a cheaper staffing plan — then visualises the whole loop in a cockpit UI.

- **Engine** (`src/`, `eval/`) — walk-forward adjustment engine + belief-graph curation. Scored in €
  on the daily operative person-day total. Beats the B2 baseline (93.03% gap closed on training,
  95.0% out-of-sample September).
- **API** (`api/`) — FastAPI read-only surface over the engine.
- **Web** (`web/`) — React + Vite cockpit (knowledge graph, staffing, compounding, decision trace,
  synthetic robustness).
- **Bot** (`bot/`) — optional Discord absence loop.

## Run the whole thing (one line)

```bash
docker compose up --build
```

Then open **http://localhost:5173**. (The API is also exposed directly on http://localhost:8000 — see
the interactive contract at http://localhost:8000/docs.)

That single command builds and starts both services; nginx in the web container proxies `/api` to the
API container, so there's nothing else to wire up. Stop with `Ctrl-C`, or `docker compose down`.

### Optional: the Discord bot

Needs Discord credentials in `.env` (copy `.env.example`). Then:

```bash
docker compose --profile bot up --build
```

### Optional: the LLM layer

The scored engine runs fully **without** any API key. To enable free-text planner-note parsing and
natural-language explanations, set `ANTHROPIC_API_KEY` in `.env` (or your shell) before starting.

## Develop locally (without Docker)

```bash
pip install -r requirements.txt
uvicorn api.main:app --port 8000      # API
cd web && npm install && npm run dev  # web (http://localhost:5173, proxies /api → :8000)
python3 -m pytest -q                  # tests
```

See `CLAUDE.md` for the documentation index and `docs/` for the design, data reference, and roadmap.
