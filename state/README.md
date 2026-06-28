# state/ — local persisted knowledge artifacts

Derived/curated knowledge that the system persists locally (instead of recomputing from CSV every
time). The raw dataset stays in `hackathon-dataset/` (the numeric source of truth); this folder holds
the **knowledge layer**. Files here are **committed and reviewed** — they are frozen inputs, not a
scratch cache. Migrate the *mutable* tier to PostgreSQL/Neon later (see `docs/TECH_DEBT.md`).

## Files
- `belief_extractions.json` — the **LLM-first extraction cache**. Per note: the structured claim
  Claude read from the prose + any `contradicts`/`supersedes` it flagged, keyed by note id and a hash
  of the note text. Regenerate with `python3 scripts/extract_beliefs.py`; **review before committing**.
  Used only by `build_graph(use_llm=True)`; the deterministic scored path ignores it.

## Contract
- Append-only for existing notes: never retroactively re-parse the past (walk-forward integrity).
  A changed note's hash mismatches → that note falls back to the hint until re-extracted with `--refresh`.
- A complete cache makes `use_llm=True` deterministic and key-independent (all entries 'fresh' → no calls).
