"""Pydantic response models — the typed contract the React frontend builds against (see /docs)."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class Breakdown(BaseModel):
    total: float
    overstaff_cost: float
    understaff_premium_cost: float
    sla_penalty_cost: float
    overstaffed_days: int
    understaffed_days: int
    sla_breach_days: int


class Summary(BaseModel):
    n_days: int
    baseline_cost: float
    engine_cost: float
    b1_flat_cost: float
    b2_adaptive_cost: float
    engine_gap_closed_pct: float
    b2_gap_closed_pct: float
    saving_vs_baseline_eur: float
    breakdown: Breakdown


class PlanRow(BaseModel):
    date: str
    weekday: str
    decision_date: str
    planned: float
    recommended: float
    # product translation layer (1 person-day = 1 person on 1 shift/day)
    target_headcount: int
    optimiser_headcount: int
    confirmed_headcount: int
    coverage: str  # "covered" | "short" (mutated by absences)
    short_by: int
    sla_risk_eur: float
    confidence: str  # "high" | "medium" | "low"
    confidence_basis: str
    reason_short: str
    est_saving_eur: float
    trim_pct: float


class Trace(BaseModel):
    date: str
    recommended: float
    regime_boundary: Optional[str]
    history_ratios: Dict[str, float]
    k: float
    level: float
    offset: float
    trend_adj: float
    planned: float
    actual: Optional[float] = None
    our_cost: Optional[float] = None
    baseline_cost: Optional[float] = None
    is_holdout: bool
    reason_text: str


class CycleRow(BaseModel):
    decision_date: str
    days: int
    engine_cost: float
    baseline_cost: float
    gap_closed_pct: float


class BeliefNode(BaseModel):
    id: str
    kind: str
    status: str
    trust: float
    activities: List[str]
    scope: str
    valid_from: str
    valid_to: Optional[str]
    author: Optional[str]
    note: str
    contribution_eur: float
    evidence: List[str]


class GraphEdge(BaseModel):
    src: str
    dst: str
    kind: str


class Graph(BaseModel):
    as_of: Optional[str]
    nodes: List[BeliefNode]
    edges: List[GraphEdge]


class CompoundingPoint(BaseModel):
    decision_date: str
    statuses: Dict[str, str]
    cycle_cost: float
    cycle_baseline: float
    cum_gap_pct: float


class AblationRow(BaseModel):
    id: str
    contribution_eur: float


class Validation(BaseModel):
    ablation: List[AblationRow]
    sensitivity: Dict[str, float]
    noise_floor: Dict[str, float]


class Absence(BaseModel):
    id: int
    worker: str
    date: str
    reason: str
    source: str
    status: str  # open | resolved
    resolution: Optional[str] = None
    created_at: str


class AbsenceCreate(BaseModel):
    worker: str
    date: str
    reason: str = ""
    source: str = "app"


class AbsenceImpact(BaseModel):
    absence: Absence
    date: str
    weekday: str
    target_headcount: int
    confirmed_headcount: int
    short_by: int
    sla_risk_eur: float
    sla_breach: bool  # shortfall beyond the 2.0 tolerance → €600/day penalty territory
    recommendation: str
    message: str  # human-readable line the bot echoes back to Discord


class ResolveRequest(BaseModel):
    option: str  # "filled" | "accepted"


class NoteInterpretation(BaseModel):
    scope: str
    kind: str
    summary: str
    is_one_off: bool
    confidence: float
    influence_note: str


class NotePreviewRequest(BaseModel):
    text: str
    author: Optional[str] = None


class NotePreviewResponse(BaseModel):
    interpretation: NoteInterpretation
    parsed: Optional[Dict] = None
    raw_text: str
    author: Optional[str] = None
    note_id: str
    llm_used: bool


class NoteCommitRequest(BaseModel):
    text: str
    author: Optional[str] = None
    parsed: Optional[Dict] = None


class LlmStatus(BaseModel):
    available: bool
    model: str


class Explain(BaseModel):
    date: str
    text: str
    llm_used: bool


class AskRequest(BaseModel):
    date: str
    question: str


class AskResponse(BaseModel):
    date: str
    question: str
    answer: str
    llm_used: bool
