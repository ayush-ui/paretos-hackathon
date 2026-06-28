"""Persistence adapter — one small interface between the app's mutable state and where it lives.

Today everything lives in local JSON under `state/` (no network, no DB — the engine runs fully
offline, which is what we want for a live demo). But planner notes, absences, graph snapshots and
trust history are *mutable* state that a real deployment would want durable + multi-user. So they sit
behind this tiny `Persistence` interface; swapping the file backend for PostgreSQL/Neon later is a
single new class + one line in `get_persistence()` — nothing else in the app changes. See TECH_DEBT.

Interface (deliberately minimal — a namespaced key/value blob store):
    load(collection) -> dict | None       read a collection's blob ({} shape is the caller's contract)
    save(collection, blob)                 atomically persist a collection's blob
    exists(collection) -> bool
    delete(collection)

A "collection" is a logical name ('notes', 'absences', 'graph_snapshot', ...). The file backend maps
each to `state/<collection>.json`; a SQL backend would map each to a row/table. Callers never learn
which backend they got.
"""
from __future__ import annotations

import json
import os
import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional

from src import data

STATE_DIR = os.path.join(data.PROJECT_ROOT, "state")


class Persistence(ABC):
    """The swap seam. Implement these four methods for any backend (file now, Postgres/Neon later)."""

    @abstractmethod
    def load(self, collection: str) -> Optional[Dict]: ...

    @abstractmethod
    def save(self, collection: str, blob: Dict) -> None: ...

    @abstractmethod
    def exists(self, collection: str) -> bool: ...

    @abstractmethod
    def delete(self, collection: str) -> None: ...


class FileStore(Persistence):
    """Local-file backend: one JSON file per collection under `state/`. Atomic writes (tmp+replace),
    thread-safe. This is the offline fallback — always available, no credentials, no network."""

    def __init__(self, root: str = STATE_DIR):
        self.root = root
        self._lock = threading.Lock()
        os.makedirs(self.root, exist_ok=True)

    def _path(self, collection: str) -> str:
        safe = collection.replace("/", "_")
        return os.path.join(self.root, f"{safe}.json")

    def load(self, collection: str) -> Optional[Dict]:
        path = self._path(collection)
        if not os.path.exists(path):
            return None
        try:
            with open(path) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    def save(self, collection: str, blob: Dict) -> None:
        with self._lock:
            path = self._path(collection)
            tmp = path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(blob, fh, indent=2, default=str)
            os.replace(tmp, path)

    def exists(self, collection: str) -> bool:
        return os.path.exists(self._path(collection))

    def delete(self, collection: str) -> None:
        with self._lock:
            try:
                os.remove(self._path(collection))
            except OSError:
                pass


# --- backend selection (the one-line swap point) -----------------------------------------
_PERSISTENCE: Optional[Persistence] = None


def get_persistence() -> Persistence:
    """Return the configured backend. Defaults to the local FileStore (offline-safe).

    To migrate the mutable-state tier to PostgreSQL/Neon later: implement a `PostgresStore(Persistence)`
    (one new class), then select it here when `DATABASE_URL` is set — e.g.::

        url = os.getenv("DATABASE_URL")
        if url:
            from src.persistence_postgres import PostgresStore
            return PostgresStore(url)

    Everything else (NoteStore, AbsenceStore, AppState graph-snapshot persistence) is unchanged because
    they only depend on this interface. We keep the FileStore as a fallback so the engine still runs if
    the DB is unreachable.
    """
    global _PERSISTENCE
    if _PERSISTENCE is None:
        # NOTE: the Postgres branch is intentionally not wired yet (no DB dependency in the repo).
        # When DATABASE_URL is provided and a PostgresStore exists, select it here; until then the
        # local FileStore is the single source of mutable state. See docs/TECH_DEBT.md.
        _PERSISTENCE = FileStore()
    return _PERSISTENCE


def set_persistence(backend: Persistence) -> None:
    """Override the backend (tests / dependency injection)."""
    global _PERSISTENCE
    _PERSISTENCE = backend
