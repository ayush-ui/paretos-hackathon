"""FastAPI app — read-only HTTP surface over the precomputed engine state.

Run (dev):  uvicorn api.main:app --reload --port 8000
Docs:       http://localhost:8000/docs

Both frontend modes (Normal 'Planner's Desk', Advanced 'Knowledge Cockpit') are served from this
one surface. The API never exposes or depends on holdout actuals (ANTI_REWARD_HACKING.md): holdout
trace responses carry is_holdout=true and omit actual/cost.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from api import schemas
from api.absences import get_store
from api.state import get_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_state()  # build the engine + baselines once at boot
    yield


app = FastAPI(
    title="Helios Compounding Staffing Engine API",
    description="Belief-graph-governed staffing optimiser for the warehouse hackathon.",
    version="1.0.0",
    lifespan=lifespan,
)

# Vite dev server origins; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/summary", response_model=schemas.Summary)
def summary():
    return get_state().summary()


@app.get("/api/cycles", response_model=List[schemas.CycleRow])
def cycles():
    return get_state().cycles()


@app.get("/api/plan/current", response_model=List[schemas.PlanRow])
def plan_current():
    return get_state().current_plan()


@app.get("/api/plan/{date}/trace", response_model=schemas.Trace)
def plan_trace(date: str):
    t = get_state().trace(date)
    if t is None:
        raise HTTPException(404, f"no decision cycle covers date {date}")
    return t


@app.get("/api/graph", response_model=schemas.Graph)
def graph(as_of: Optional[str] = Query(None, description="ISO date; snapshot as the graph looked then")):
    return get_state().graph_snapshot(as_of)


@app.get("/api/provenance")
def provenance(as_of: Optional[str] = Query(None, description="ISO date; trim to weeks decided before then")):
    """Provenance KG (Source/Belief/Decision/Outcome + INFORMED/RESULTED_IN/UPDATED/PRECEDED edges).
    The audit trail: trace a plan -> belief -> note -> € outcome -> trust update -> next week."""
    return get_state().provenance(as_of)


@app.get("/api/provenance/{week}/trace")
def provenance_trace(week: str):
    """Trace one decision week back to the beliefs + notes that informed it, forward to its outcome."""
    t = get_state().provenance_trace(week)
    if t is None:
        raise HTTPException(404, f"no decision week {week} in the provenance graph")
    return t


@app.get("/api/staffing")
def staffing():
    """Per-week operative person-days: our plan vs optimiser vs realized actual (holdout omits actual)."""
    return get_state().staffing_series()


@app.get("/api/synthetic")
def synthetic_stress():
    """SYNTHETIC robustness panel: frozen engine vs no-knowledge ablation across regime worlds."""
    return get_state().synthetic_stress()


@app.get("/api/trust")
def trust_trajectory():
    """Week-by-week shadow-trust EWMA curve per belief (observability for the trust-over-time view).
    Shadow of the real forward-pruning curation, not a replacement for it."""
    return get_state().trust_trajectory()


@app.get("/api/beliefs/{belief_id}", response_model=schemas.BeliefNode)
def belief(belief_id: str):
    b = get_state().belief(belief_id)
    if b is None:
        raise HTTPException(404, f"no belief {belief_id}")
    return b


@app.get("/api/compounding", response_model=List[schemas.CompoundingPoint])
def compounding():
    return get_state().compounding()


@app.get("/api/validation", response_model=schemas.Validation)
def validation():
    return get_state().validation()


@app.get("/api/plan/dates")
def plan_dates():
    """Plannable {date, weekday} list — used by the Discord bot to map free text to a real plan date."""
    return get_state().plan_dates()


# --- absences (Discord operational loop) ------------------------------------------------
@app.get("/api/absences", response_model=List[schemas.Absence])
def list_absences():
    return get_store().list()


@app.post("/api/absences", response_model=schemas.AbsenceImpact)
def create_absence(body: schemas.AbsenceCreate):
    rec = get_store().add(body.worker, body.date, body.reason, body.source)
    return get_state().absence_impact(rec)


@app.post("/api/absences/{absence_id}/resolve", response_model=schemas.Absence)
def resolve_absence(absence_id: int, body: schemas.ResolveRequest):
    if body.option not in ("filled", "accepted"):
        raise HTTPException(422, "option must be 'filled' or 'accepted'")
    rec = get_store().resolve(absence_id, body.option)
    if rec is None:
        raise HTTPException(404, f"no absence {absence_id}")
    return rec


@app.delete("/api/absences")
def clear_absences():
    """Demo convenience: wipe all absences."""
    get_store().clear()
    return {"status": "cleared"}


# --- planner notes (human-in-the-loop knowledge capture) --------------------------------
@app.post("/api/notes/preview", response_model=schemas.NotePreviewResponse)
def note_preview(body: schemas.NotePreviewRequest):
    """AI interpretation of a free-text planner note — no save. Drives the 'here's how I understood it'."""
    if not body.text.strip():
        raise HTTPException(422, "note text is empty")
    return get_state().note_preview(body.text, body.author)


@app.post("/api/notes", response_model=schemas.BeliefNode)
def note_commit(body: schemas.NoteCommitRequest):
    """Commit a planner note as a candidate belief in the graph."""
    if not body.text.strip():
        raise HTTPException(422, "note text is empty")
    return get_state().note_commit(body.text, body.author, body.parsed)


@app.delete("/api/notes/{note_id}")
def note_delete(note_id: str):
    if not get_state().note_delete(note_id):
        raise HTTPException(404, f"no planner note {note_id}")
    return {"status": "deleted", "id": note_id}


@app.get("/api/llm/status", response_model=schemas.LlmStatus)
def llm_status():
    return get_state().llm_status()


@app.get("/api/plan/{date}/explain", response_model=schemas.Explain)
def explain(date: str):
    """Natural-language 'why this number' (LLM if configured, deterministic template otherwise)."""
    out = get_state().explain(date)
    if out is None:
        raise HTTPException(404, f"no decision cycle covers date {date}")
    return out


@app.post("/api/ask", response_model=schemas.AskResponse)
def ask(req: schemas.AskRequest):
    """Advanced-mode 'ask why' — grounded only in the verified trace + summary for that date."""
    out = get_state().ask(req.date, req.question)
    if out is None:
        raise HTTPException(404, f"no decision cycle covers date {req.date}")
    return out
