"""LLM-first belief extraction with a deterministic fallback (the merge's knowledge-ingestion layer).

Two ways a decision-log note becomes a structured belief:
  1. **LLM-first** — Claude reads the note's *prose* (one note at a time, in date order, with the
     beliefs already learned from earlier notes as context) and emits a richer `claimed_effect`,
     flagging `contradicts` / `supersedes` from the language itself (e.g. L09 disputing L08, L11/L12
     retiring L03). This captures nuance the pre-baked hint flattens, and is what the track rewards.
  2. **Deterministic fallback** — with no API key (or LLM failure) we read the structured
     `claimed_effect` hint already in the dataset. Identical behaviour to the original pipeline.

Honesty / determinism contract (see docs/MERGE_PLAN.md, docs/ANTI_REWARD_HACKING.md):
  - The extraction is **cached** (state/belief_extractions.json), keyed by note id + a hash of the
    note text. Once generated and **human-reviewed**, the cache is the frozen, deterministic input
    to the scored backtest — re-running never silently re-parses the past (walk-forward integrity).
  - `extracted_beliefs(use_llm=False)` (the default) uses ONLY the cache-or-hint, makes **no network
    call**, and reproduces the locked numbers. `use_llm=True` may call the LLM to FILL cache misses,
    then caches them. New notes append; existing entries are never retroactively rewritten unless
    `refresh=True` is passed explicitly.
  - The LLM still only PROPOSES a claim; curation (src/curate.py) decides trust/expiry. The LLM never
    sets a staffing number.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from . import beliefs, data, llm
from .beliefs import Belief, Edge

# The reviewed, frozen extraction cache lives in the local state/ folder (committed, not gitignored).
STATE_DIR = os.path.join(data.PROJECT_ROOT, "state")
CACHE_PATH = os.path.join(STATE_DIR, "belief_extractions.json")

_KINDS = "fixed | scale_pct | add | conditional_trim | conditional_add | trend | note"


class LlmClaim(BaseModel):
    """The structured belief the LLM reads out of a note's prose — a richer `claimed_effect`.

    Field names mirror the dataset's hint so one builder (beliefs.belief_from_entry) handles both.
    """
    kind: str = Field(description=f"One of: {_KINDS}")
    scope: Optional[str] = Field(None, description="'operative' (moves the whole-site total) or 'activity'.")
    activity: Optional[str] = Field(None, description="Single canonical activity name, if activity-scoped.")
    activities: Optional[List[str]] = Field(None, description="Several canonical activity names, if many.")
    value: Optional[float] = Field(None, description="Fixed crew size, for kind=fixed.")
    pct: Optional[float] = Field(None, description="Percent change (negative=cut), for kind=scale_pct.")
    delta: Optional[float] = Field(None, description="Person-day change, for add/conditional kinds.")
    weekday: Optional[str] = Field(None, description="'Mon' | 'payday-Mon' | null.")
    when: Optional[str] = Field(None, description="Condition: 'picks < 7000' | 'inbound > 2000' | 'day-after-closure' | null.")
    effective_from: Optional[str] = Field(None, description="ISO date a regime change takes effect (e.g. pick-by-light), else null.")
    trend: Optional[str] = Field(None, description="'up' | 'down' | null, for kind=trend/note.")
    contradicts: List[str] = Field(default_factory=list, description="ids of EARLIER beliefs this note opposes (from the provided known list only).")
    supersedes: List[str] = Field(default_factory=list, description="ids of EARLIER beliefs this note retires/makes stale (known list only).")
    rationale: str = Field("", description="One sentence: what this belief claims.")
    confidence: float = Field(0.5, description="0..1 how strongly the prose supports a durable rule.")

    def to_claimed_effect(self) -> Dict:
        """Project onto a dataset-shaped `claimed_effect` dict (drop nulls, map effective_from->from)."""
        d: Dict = {"kind": self.kind}
        if self.scope:
            d["scope"] = self.scope
        if self.activity:
            d["activity"] = self.activity
        if self.activities:
            d["activities"] = self.activities
        for k in ("value", "pct", "delta", "weekday", "trend"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        if self.when:
            d["when"] = self.when
        if self.effective_from:
            d["from"] = self.effective_from
        return d


def _system() -> str:
    acts = ", ".join(data.OPERATIVE_ACTIVITIES)
    return (
        "You are a warehouse planning analyst. A deterministic optimiser publishes a staffing plan; it "
        "systematically OVERSTAFFS. We plan the OPERATIVE total per day and are scored against the labour "
        "that actually worked. Convert ONE planner note into a structured belief about how the plan "
        "diverges from reality. Read negations carefully ('we needed more, do not cut' => staff MORE). "
        "scope='operative' ONLY if it moves the whole-site total; else 'activity'. kind=trend/note for a "
        "lasting forward shift or a non-numeric observation. If the note opposes or retires an EARLIER "
        "belief in the provided list, put its id in contradicts/supersedes (use only ids from that list). "
        f"Canonical operative activities: {acts}."
    )


def _prompt(entry: Dict, known: List[Belief]) -> str:
    known_txt = "\n".join(
        f"  [{b.id}] {b.kind} dir/effect: {b.note[:60]}" for b in known) or "  (none yet)"
    claim = entry.get("claimed_effect", {})
    return (
        f"Beliefs already learned from EARLIER notes (you may reference these ids):\n{known_txt}\n\n"
        f"NEW note (id {entry['id']}, written {entry['captured_on']} by {entry.get('author')}, "
        f"machine hint={json.dumps(claim)}):\n\"\"\"\n{entry['note']}\n\"\"\"\n\nExtract one structured belief."
    )


def _note_hash(entry: Dict) -> str:
    return hashlib.sha256(entry["note"].encode("utf-8")).hexdigest()[:12]


def load_cache(path: Optional[str] = None) -> Dict:
    path = path or CACHE_PATH
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    return {}


def save_cache(cache: Dict, path: Optional[str] = None) -> None:
    path = path or CACHE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(cache, fh, indent=2, sort_keys=True)


def extracted_beliefs(log_path: Optional[str] = None, use_llm: bool = False,
                      cache_path: Optional[str] = None, refresh: bool = False
                      ) -> Tuple[List[Belief], List[Edge]]:
    """Return (beliefs, llm_edges) from the decision log.

    use_llm=False (default): cache-or-hint only, no network, deterministic — the scored path.
    use_llm=True: fill cache misses via the LLM (if available), persist, and use the result.
    """
    log = beliefs.load_log(log_path)
    # The cache is the LLM-first artifact; the pure-hint fallback ignores it entirely so it is always
    # deterministic and key-independent. A complete cache makes use_llm=True deterministic too (no calls).
    cache = load_cache(cache_path) if use_llm else {}
    out: List[Belief] = []
    edges: List[Edge] = []
    known: List[Belief] = []
    dirty = False

    for e in log["entries"]:
        cid = e["id"]
        cached = cache.get(cid)
        fresh = cached is not None and cached.get("note_hash") == _note_hash(e) and not refresh
        claim = None
        if fresh:
            claim = cached["claim"]
        elif use_llm and llm.available():
            parsed = llm.parse(_prompt(e, known), LlmClaim, system=_system())
            if parsed is not None:
                claim = parsed.to_claimed_effect()
                cache[cid] = {"note_hash": _note_hash(e), "claim": claim,
                              "contradicts": parsed.contradicts, "supersedes": parsed.supersedes,
                              "rationale": parsed.rationale, "confidence": parsed.confidence}
                dirty = True
        # build belief from the LLM claim if we have one, else the dataset hint (fallback)
        tag = "llm-extracted" if claim is not None else "decision_log"
        b = beliefs.belief_from_entry(e, claim=claim, evidence_tag=tag)
        out.append(b)
        known.append(b)
        rec = cache.get(cid, {})
        for tgt in rec.get("supersedes", []):
            edges.append(Edge(cid, tgt, "supersedes"))
        for tgt in rec.get("contradicts", []):
            edges.append(Edge(cid, tgt, "contradicts"))

    if dirty and use_llm:
        save_cache(cache, cache_path)
    return out, edges
