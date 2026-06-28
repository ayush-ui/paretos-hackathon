# PRODUCT_PLAN.md — Making Helios usable: legibility, Discord, two-tier UI

> Decided 2026-06-28 with paretos. Problem statement: the app currently shows optimisation internals
> (person-days, trim %, gap-closed) that a **shift planner cannot act on**. This plan reframes the
> product around the planner's real job, adds a live absence loop via Discord, and splits the UI into
> a planner-facing Normal mode and a knowledge-engineer-facing Advanced mode. Engine math is unchanged
> and stays honest (walk-forward, no holdout peeking — ANTI_REWARD_HACKING.md).

## 0. The core insight — a translation layer
The engine predicts the **daily operative person-day total** (what it's scored on). A planner thinks in
**people and coverage**. The missing layer:
```
engine person-days  →  headcount        →  roster            →  coverage & risk
58.5                   round() = 59        59 named slots        58 confirmed → 1 SHORT, SLA risk €X
```
**Decisions:** 1 person-day = 1 person on 1 shift/day → `headcount = round(person_days)`. The dataset
has **no named workers**, so the roster (named people / who's on which day) is a **synthesised product
layer** on top of the real numbers — labelled in-app so it's never misleading. Absences (Discord)
mutate `confirmed` vs `target`; the engine's cost asymmetry quantifies the € impact of a gap.

## 1. Workstream A — Legible "Planner's Desk" (Normal mode)  [BUILD FIRST]
Persona: shift manager, non-technical. Wants headcount + safety + actions.
- **This-week view:** 7 day-cards. Each: big **"Staff N people"**, optimiser N faded, **coverage bar**
  (confirmed vs target), **confidence badge** (model certainty), **one plain-English sentence**.
- **Mini chart:** demand (optimiser) vs staffing (plan) across the week — legible, not a knowledge graph.
- **Per-day Accept / Adjust** with live €/risk feedback.
- **Track record strip** (from /api/summary): "saved €X vs. doing nothing."
- **"About this plan" explainer** — one paragraph in plain words so a first-time user gets it.
- Honest confidence: derived from the stability (coeff. of variation) of the recent regime ratios;
  **capped at "medium" for October** because the holdout is a forecast beyond observed data.

## 2. Workstream B — Discord absence loop (operational)  [NEEDS paretos INPUT]
Persona: operative reports an absence; planner resolves it.
**Journey:** worker types free-text in Discord ("can't make Tue, sick") → bot → **LLM parses** (reuse
`src/note_parser.py`) → `POST /api/absences {worker,date,reason}` → backend recomputes the day:
target 59, confirmed 58 → **"Tuesday 1 short, expected SLA penalty ~€X"** → planner sees a badge →
**Resolve flow** offers engine-costed options (call standby +€Y removes €X risk / overtime / accept
gap) → pick → plan updated + logged. **Compounding climax:** recurring absence patterns become
**candidate beliefs** in the graph → curated → future plans pre-buffer those days.
**Interaction style chosen:** free-text + LLM parsing (needs the privileged **Message Content intent**).

### What we need from paretos (to start Workstream B)
1. **Bot token** (Discord Developer Portal → application → Bot → token).
2. **Guild (server) ID** + **channel ID(s)** for absence reports (Developer Mode → Copy ID).
3. **Worker ↔ Discord identity** mapping (a `/register name:…` command, or a provided list).
4. Confirm running the bot as a persistent **discord.py gateway process** locally (no public URL needed);
   else we use an Interactions Endpoint URL + ngrok.
5. Enable the **Message Content intent** in the portal (required for free-text parsing).
Helios side: bot code, `/api/absences` + roster model, Resolve UI, pattern→belief feed.

## 3. Workstream C — Advanced "Knowledge Cockpit" (master control)  [BUILD AFTER A]
Persona: technical/ops analyst. Unlocked by the Advanced toggle.
1. **Belief graph (React Flow)** — beliefs as nodes, supersedes/contradicts/reaffirms edges, colored by
   status; click → claim, author, € contribution, evidence, lifecycle.
2. **Time-slider (`as_of`)** — scrub weeks, watch beliefs activate/retire (compounding, animated).
3. **Decision trace** — any day → optimiser→trim→regime→offset→trend→final + cost. (The "why this number"
   that explains the raw table.)
4. **Validation panel** — ablation (€/belief), sensitivity, noise floor (anti-overfit proof).
5. **Curation controls** — promote/retire beliefs, accept/reject candidates (incl. LLM-proposed ones from
   Discord patterns / notes). The "master level control over the knowledge."
Why it matters: the graph is the visual proof that knowledge is captured, governed, and paying off —
the heart of the "compounding decisions" pitch. Hidden from the everyday planner behind the toggle.

## 4. Strategic sequence
```
Step 0  Translation layer (person-days→headcount→coverage, honest confidence)   [unblocks all]
Step 1  Workstream A — legible Planner's Desk + explainer + track record         ← CURRENT
Step 2  Workstream B — Discord bot + /api/absences + Resolve flow (needs input)
Step 3  Workstream C — Advanced graph + trace + time-slider + validation + curation
Step 4  Wire Discord patterns → candidate beliefs (climax) + polish + demo script
```
Order rationale: legibility is the current blocker → first. Discord needs paretos lead-time → request
now, build next. Advanced is self-contained → last. Step 4 connects B→C for the narrative finale.
```
