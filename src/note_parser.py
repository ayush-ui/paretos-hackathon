"""(A) Free-text note -> structured candidate hypothesis.

This is the capability that lets the system ingest RAW human language (e.g. "drivers were tired due
to the heat wave", "Max couldn't show up, his kid was sick") instead of relying on the pre-baked
`claimed_effect` field. The LLM PROPOSES a structured, testable hypothesis; it does NOT decide truth.
Every parsed note becomes a CANDIDATE belief that must still earn trust through the deterministic
curation gate (src/curate.py) before it can influence a staffing number.

With no ANTHROPIC_API_KEY, `parse_note` returns None and callers fall back to the structured
`claimed_effect` already in the dataset — the deterministic pipeline is unchanged.
"""
from __future__ import annotations

from typing import List, Optional

try:
    from typing import Literal
except ImportError:  # py<3.8 safety
    Literal = None

from pydantic import BaseModel, Field

from . import data, llm
from .beliefs import Belief, ACTIVITY_KEY

_KINDS = "fixed | scale_pct | add | conditional_trim | conditional_add | trend | note"


class ParsedNote(BaseModel):
    """A structured, testable hypothesis extracted from a free-text planner note. A CLAIM, not a fact."""
    kind: str = Field(description=f"One of: {_KINDS}")
    activities: List[str] = Field(
        default_factory=list,
        description="Canonical activity names this note touches; empty for whole-operative or pure notes.")
    value: Optional[float] = Field(None, description="Fixed crew size, for kind=fixed.")
    pct: Optional[float] = Field(None, description="Percent change (negative=cut), for kind=scale_pct.")
    delta: Optional[float] = Field(None, description="Person-day change, for add/conditional kinds.")
    weekday: Optional[str] = Field(None, description="'Mon' | 'payday-Mon' | null.")
    condition: Optional[str] = Field(
        None, description="Trigger like 'picks < 7000', 'inbound > 2000', 'day-after-closure', or null.")
    trend: Optional[str] = Field(None, description="'up' | 'down' | null, for kind=trend/note.")
    is_one_off: bool = Field(
        description="True if this reads as a single random incident (e.g. a specific person absent) that "
                    "should NOT become a recurring rule; False if it proposes a repeatable pattern.")
    confidence: float = Field(description="0..1 — how strongly the text supports a durable, testable rule.")
    rationale: str = Field(description="One sentence: what pattern (if any) this proposes and why.")


def _system() -> str:
    acts = ", ".join(data.OPERATIVE_ACTIVITIES)
    return (
        "You convert a warehouse planner's messy free-text note into ONE structured, testable "
        "hypothesis about how the staffing optimiser's plan diverges from reality. You only PROPOSE "
        "a claim; a separate system validates it against actuals. Be conservative: if a note describes "
        "a single random incident (a specific person absent, a one-time event) set is_one_off=true and "
        "low confidence — it must not become a recurring rule. "
        f"Canonical operative activities: {acts}. "
        "Map activity mentions to these names; use an empty list for whole-operative or non-numeric notes."
    )


def parse_note(text: str, captured_on: str = "2026-01-01", note_id: Optional[str] = None) -> Optional[ParsedNote]:
    """Parse one free-text note into a ParsedNote. Returns None if the LLM is unavailable."""
    prompt = f"Planner note (captured {captured_on}):\n\"\"\"\n{text}\n\"\"\"\n\nExtract one hypothesis."
    return llm.parse(prompt, ParsedNote, system=_system())


def to_candidate_belief(parsed: ParsedNote, note_id: str, captured_on: str,
                        author: Optional[str] = None, note_text: str = "") -> Belief:
    """Convert a ParsedNote into a CANDIDATE Belief for the graph. Not trusted until curation says so.

    A one-off stays a candidate with near-zero trust and is parked as attribution, never promoted to
    a recurring rule — exactly the 'explain a day vs generalise a rule' distinction.
    """
    params = {}
    if parsed.value is not None:
        params["value"] = parsed.value
    if parsed.pct is not None:
        params["pct"] = parsed.pct
    if parsed.delta is not None:
        params["delta"] = parsed.delta
    if parsed.trend is not None:
        params["trend"] = parsed.trend
    # accept canonical names ('Picking') or loose keys ('picking') the model may emit
    canon = set(data.OPERATIVE_ACTIVITIES)
    acts = []
    for a in parsed.activities:
        if a in canon:
            acts.append(a)
        elif a.lower() in ACTIVITY_KEY:
            acts.append(ACTIVITY_KEY[a.lower()])
    b = Belief(
        id=note_id, source="log", kind=parsed.kind,
        activities=acts,
        params=params, valid_from=captured_on, weekday=parsed.weekday, condition=parsed.condition,
        trust=0.0 if parsed.is_one_off else min(0.5, parsed.confidence),
        status="candidate", author=author, note=note_text or parsed.rationale,
        evidence=[f"llm-parsed:{note_id} (one_off={parsed.is_one_off}, conf={parsed.confidence:.2f})"],
    )
    return b
