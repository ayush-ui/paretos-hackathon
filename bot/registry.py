"""Tiny worker registry — maps a Discord user to a chosen worker name.

Used by /register so a member can enroll once and have their absences logged under a name they pick
(rather than their raw Discord display name). JSON-persisted, gitignored. Bot-local: registration is
only needed at message time, so it doesn't need to go through the API.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Dict, Optional

_PATH = os.path.join(os.path.dirname(__file__), "_registrations.json")
_lock = threading.Lock()


def _load() -> Dict[str, Dict]:
    if os.path.exists(_PATH):
        try:
            with open(_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(data: Dict[str, Dict]) -> None:
    tmp = _PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, _PATH)


def register(discord_id: int, name: str) -> None:
    with _lock:
        data = _load()
        data[str(discord_id)] = {"name": name}
        _save(data)


def name_for(discord_id: int, fallback: str) -> str:
    """Registered name if the user enrolled, else the given fallback (their Discord display name)."""
    rec = _load().get(str(discord_id))
    return rec["name"] if rec else fallback


def is_registered(discord_id: int) -> bool:
    return str(discord_id) in _load()
