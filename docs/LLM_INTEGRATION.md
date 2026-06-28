# LLM_INTEGRATION.md — where (and where NOT) the LLM is used

> Provider: **Anthropic Claude** (`claude-opus-4-8`). The LLM is **optional and additive**. With no
> `ANTHROPIC_API_KEY`, the whole system runs exactly as the deterministic engine does — the numbers
> are byte-for-byte identical (test: `tests/test_llm.py::TestNumbersUnaffectedByLlm`).

## The one rule
**The LLM proposes and explains; the deterministic backtest is the sole arbiter of truth.** It never
generates or adjusts a staffing number, and never decides whether a belief is true. This preserves
everything Phase 5 proved (grounded, walk-forward, verifiable).

## Two integration points
**(A) Note parsing — `src/note_parser.py`.** Turns a RAW free-text planner note ("drivers were tired
from the heat wave", "Max couldn't show up, kid was sick") into a structured `ParsedNote` hypothesis,
including an `is_one_off` flag (single random incident vs repeatable pattern) and a `confidence`.
- Output is a **candidate** belief (`to_candidate_belief`) with trust ≤ 0.5 (0.0 for one-offs). It then
  must pass the SAME `src/curate.py` gate as every other belief before it can influence a number.
- A one-off is parked as attribution, never promoted to a recurring rule.
- This is a *capability demo* — the shipped dataset already has structured `claimed_effect`, so the
  core pipeline does not depend on it. It proves the system can ingest real human language.

**(B) Explanation & Q&A — `src/narrator.py`.** Rephrases an ALREADY-VERIFIED trace into plain English
for the Normal UI, and answers "why did we staff N on day X?" in Advanced mode. It is given only
numbers the engine already computed → no hallucination risk to the plan (worst case: awkward prose).

## API surface (all degrade gracefully)
- `GET /api/llm/status` → `{available, model}`.
- `GET /api/plan/{date}/explain` → `{date, text, llm_used}`. LLM narration if available, else the
  deterministic template reason. `reason_text` on the trace stays template-based (instant, free).
- `POST /api/ask` `{date, question}` → `{answer, llm_used}`. Grounded only in that date's verified
  trace + the summary; says so if the LLM isn't configured.

LLM calls happen **on demand** (explain/ask), never during plan computation or startup — so the
default experience is fast and free, and cost is only incurred when a user clicks "explain"/"ask".

## Activating it
```bash
pip install -r requirements.txt        # includes anthropic
export ANTHROPIC_API_KEY=sk-ant-...     # do NOT commit this
uvicorn api.main:app --reload --port 8000
# GET /api/llm/status now reports available: true
```
`src/llm.py` is the single choke point: model id, `available()`, `narrate()`, `parse()`, and the
try/except that returns `None` (→ deterministic fallback) on any error.

## Anti-reward-hacking notes
- The LLM never sees or emits holdout actuals; `explain`/`ask` on a holdout day carry no actual/cost.
- Parsed notes respect `captured_on` as `valid_from` (walk-forward), same as hand-authored beliefs.
- Live-LLM output is non-deterministic and is NOT unit-tested; only the deterministic fallback and the
  candidate-belief schema are. Don't gate correctness on a live call.
