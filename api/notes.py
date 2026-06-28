"""Planner-note capture — the human-in-the-loop side of the compounding graph.

A planner writes a free-text observation ("picking felt over-staffed all week"). The LLM (note_parser)
structures it into a testable candidate hypothesis; it becomes a CANDIDATE belief in the graph,
authored by the planner. Like every belief, it only earns influence through the deterministic curation
gate — so capturing a note records knowledge for FUTURE decisions without silently overriding the
current locked plan. State is JSON-persisted so notes survive an API restart and rebuild into the graph.

Mirrors the design rules in src/note_parser.py + docs/ANTI_REWARD_HACKING.md: the LLM PROPOSES, the
data decides. With no ANTHROPIC_API_KEY, capture still works — the note is stored as a plain candidate.
"""
from __future__ import annotations

import datetime as _dt
import threading
from typing import Dict, List, Optional

from src import note_parser
from src.beliefs import Belief
from src.persistence import Persistence, get_persistence

_COLLECTION = "notes"
_lock = threading.Lock()


class NoteStore:
    def __init__(self, backend: Optional[Persistence] = None):
        self.backend = backend or get_persistence()
        self.notes: List[Dict] = []  # each: {id, raw_text, author, created_at, parsed, belief}
        self._seq = 1
        self._load()

    # --- persistence (behind the swappable adapter; file now, Postgres/Neon later) ---------
    def _load(self) -> None:
        blob = self.backend.load(_COLLECTION)
        if blob:
            self.notes = blob.get("notes", [])
            self._seq = blob.get("seq", len(self.notes) + 1)

    def _save(self) -> None:
        self.backend.save(_COLLECTION, {"notes": self.notes, "seq": self._seq})

    def next_id(self) -> str:
        return f"P{self._seq:02d}"

    def add(self, rec: Dict) -> None:
        with _lock:
            self.notes.append(rec)
            self._seq += 1
            self._save()

    def delete(self, note_id: str) -> bool:
        with _lock:
            before = len(self.notes)
            self.notes = [n for n in self.notes if n["id"] != note_id]
            if len(self.notes) != before:
                self._save()
                return True
            return False

    def list(self) -> List[Dict]:
        return list(self.notes)


_STORE: Optional[NoteStore] = None


def get_store() -> NoteStore:
    global _STORE
    if _STORE is None:
        _STORE = NoteStore()
    return _STORE


# --- parsing / belief construction --------------------------------------------------------
def _scope_of(b: Belief) -> str:
    return ", ".join(b.activities) or "whole operation"


def interpret(text: str, author: Optional[str], captured_on: str, note_id: str) -> Dict:
    """Run the LLM interpretation of a note WITHOUT saving. Returns a display-friendly draft plus the
    raw parsed fields (so commit doesn't have to re-call the LLM). Falls back to a plain note off-LLM."""
    parsed = note_parser.parse_note(text, captured_on=captured_on, note_id=note_id)
    llm_used = parsed is not None
    if parsed is not None:
        belief = note_parser.to_candidate_belief(parsed, note_id, captured_on, author=author, note_text=text)
        parsed_dict = parsed.model_dump()
        summary = parsed.rationale
        one_off = parsed.is_one_off
        confidence = parsed.confidence
    else:
        belief = Belief(id=note_id, source="log", kind="note", activities=[], valid_from=captured_on,
                        trust=0.1, status="candidate", author=author, note=text,
                        evidence=[f"planner-note:{note_id} (no-llm)"])
        parsed_dict = None
        summary = text
        one_off = False
        confidence = 0.3
    return {
        "interpretation": {
            "scope": _scope_of(belief),
            "kind": belief.kind,
            "summary": summary,
            "is_one_off": one_off,
            "confidence": round(confidence, 2),
            "influence_note": (
                "Recorded as a one-off — kept for the record, won't become a recurring rule."
                if one_off else
                "Added as a candidate — the engine will test it against upcoming weeks before it changes the plan."
            ),
        },
        "parsed": parsed_dict,
        "raw_text": text,
        "author": author,
        "note_id": note_id,
        "llm_used": llm_used,
    }


def build_belief(text: str, author: Optional[str], captured_on: str, note_id: str,
                 parsed: Optional[Dict]) -> Belief:
    """Reconstruct the candidate Belief to commit. Uses the parsed fields from preview when present
    (no second LLM call); re-parses or falls back to a plain note otherwise."""
    if parsed is not None:
        pn = note_parser.ParsedNote(**parsed)
        return note_parser.to_candidate_belief(pn, note_id, captured_on, author=author, note_text=text)
    draft = interpret(text, author, captured_on, note_id)
    if draft["parsed"] is not None:
        pn = note_parser.ParsedNote(**draft["parsed"])
        return note_parser.to_candidate_belief(pn, note_id, captured_on, author=author, note_text=text)
    return Belief(id=note_id, source="log", kind="note", activities=[], valid_from=captured_on,
                  trust=0.1, status="candidate", author=author, note=text,
                  evidence=[f"planner-note:{note_id} (no-llm)"])
