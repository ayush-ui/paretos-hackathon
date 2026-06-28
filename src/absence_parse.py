"""Parse a free-text Discord absence message into a structured {date, reason}.

Reuses the central LLM choke point (src/llm.parse). The model is given the exact list of plannable
dates so it resolves "Tuesday" / "next Mon" / "Oct 6" to a real plan date — no date arithmetic in code.
Falls back to a deterministic weekday/ISO matcher when the LLM is unavailable, so the bot still works.

Like the rest of the LLM layer: this only PROPOSES a structured interpretation of what a human typed;
it never touches the scored engine numbers.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel

from src import llm

_WEEKDAYS = {"mon": "Mon", "monday": "Mon", "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
             "wed": "Wed", "weds": "Wed", "wednesday": "Wed", "thu": "Thu", "thur": "Thu",
             "thurs": "Thu", "thursday": "Thu", "fri": "Fri", "friday": "Fri"}


class AbsenceParse(BaseModel):
    is_absence: bool          # is this message actually reporting a shift absence?
    date: Optional[str]       # one of the provided plan dates (YYYY-MM-DD), or null if unclear
    reason: str               # short reason, e.g. "sick", "family emergency"; "" if none given


def parse_absence(text: str, plan_dates: List[Dict]) -> AbsenceParse:
    """plan_dates: [{"date": "2026-10-06", "weekday": "Tue"}, ...]."""
    out = _parse_llm(text, plan_dates)
    if out is not None:
        return out
    return _parse_fallback(text, plan_dates)


def _parse_llm(text: str, plan_dates: List[Dict]) -> Optional[AbsenceParse]:
    options = "\n".join(f"  - {d['date']} ({d['weekday']})" for d in plan_dates)
    prompt = (
        "A warehouse operative sent this message in the team channel:\n\n"
        f"\"{text}\"\n\n"
        "Decide if it reports that they cannot work a shift. If so, pick the single plan date they mean "
        "from this list (and only this list):\n"
        f"{options}\n\n"
        "If they name a weekday, map it to the matching date. If no date is determinable, set date to null. "
        "Extract a short reason if given (else empty string). Set is_absence false for unrelated chatter."
    )
    return llm.parse(prompt, AbsenceParse,
                     system="You turn casual absence messages into a structured, validated record.")


def _parse_fallback(text: str, plan_dates: List[Dict]) -> AbsenceParse:
    low = text.lower()
    absent = any(w in low for w in ("can't", "cant", "cannot", "won't", "wont", "off", "absent",
                                    "not coming", "out ", "sick", "leave", "miss"))
    date = None
    # explicit ISO date present in the plan?
    for d in plan_dates:
        if d["date"] in text:
            date = d["date"]
            break
    # else first weekday mentioned → first matching plan date
    if date is None:
        for token in re.findall(r"[a-z]+", low):
            wd = _WEEKDAYS.get(token)
            if wd:
                match = next((d["date"] for d in plan_dates if d["weekday"] == wd), None)
                if match:
                    date = match
                    break
    reason = ""
    for r in ("sick", "ill", "family", "emergency", "appointment", "holiday", "leave"):
        if r in low:
            reason = r
            break
    return AbsenceParse(is_absence=absent and date is not None, date=date, reason=reason)
