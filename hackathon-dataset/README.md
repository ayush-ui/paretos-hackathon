# Compounding Decisions — Warehouse Staffing Dataset

> **Track question:** *How can AI and knowledge systems help humans understand the
> strengths and weaknesses of past decisions — so that future decisions get better
> over time?*

This dataset gives you a real-shaped supply-chain decision that **repeats every week
for six months**. Each week a planner has to commit a staffing plan, then reality
arrives and tells them how good the plan was. Your job is to build a system that
**gets smarter every week** — one that learns from what worked and what didn't, and
carries that knowledge into the next decision.

It is designed so that a single clever model run will *not* win. What wins is a loop
that **compounds**: captures a learning, applies it next cycle, notices when a
learning goes stale, and tells signal apart from noise.

---

## 1. The scenario

**Helios Logistics — DC Rhein-Main** is a fictional (anonymised) distribution centre.
Every Tuesday, a deterministic planning optimiser publishes a **staffing
recommendation** for the *following* Mon–Fri: how many person-days to put on each of
~15 operative activities (Unloading, Picking, Putaway, Loading, …) plus 4 admin desks.
It builds this from a **volume forecast** (inbound pallets, outbound pallets, picks)
divided by a fixed productivity **rate card**.

The optimiser is *fine*, not great. Its rate card was set once and never re-tuned, so
its recommendation drifts from what the warehouse actually needs. The site's planners
already know this in their gut — they quietly adjust the plan every week and jot notes
after each debrief. **Nobody has ever turned those notes into a system.** That's you.

```
        Tuesday                     following Mon–Fri                 after the week
   ┌──────────────────┐        ┌───────────────────────┐        ┌────────────────────┐
   │ optimiser issues │  ───►  │  planner DECIDES the   │  ───►  │  ACTUALS revealed:  │
   │ a recommendation │        │  staffing plan (commit)│        │ who was needed +    │
   │ (forecast ÷ rate)│        │                        │        │ what shipped        │
   └──────────────────┘        └───────────────────────┘        └─────────┬──────────┘
            ▲                                                              │
            │                      learnings carried forward              │
            └──────────────────────────────────────────────────────────◄─┘
                        capture WHY plan ≠ reality, apply it next week
```

There are **24 of these cycles**, week after week. That repetition is the whole point:
it is what lets knowledge compound — and what lets a stale belief quietly rot.

---

## 2. What's in the box

```
hackathon-dataset/
├── README.md                         ← you are here
└── data/
    ├── recommendations/              ← 24 weekly optimiser plans (rec_<decision-Tuesday>.csv)
    ├── actuals/                      ← what really happened, per training week
    │   ├── present_<week-monday>.csv     daily person-days actually on the floor
    │   └── volumes_<week-monday>.csv      realized processed volumes
    ├── clean/                        ← the same data, tidied — start here if you want
    │   ├── recommendations_long.csv
    │   ├── present_long.csv
    │   └── volumes_long.csv
    ├── decision_log.json             ← the planners' running notes (messy, unverified!)
    └── cost_model.json               ← how a staffing decision is costed
```

> The **last 4 weeks are a held-out test set.** You get their *recommendations* (so you
> can decide), but their *actuals* are withheld and kept by the facilitators for
> scoring (§5). The `clean/` files cover the training period only.

### The raw files are deliberately a little messy
Because real operational exports are. Treat parsing them as part of the warm-up — or
skip straight to `data/clean/` and come back to the raw files if you want the full
texture.

**`recommendations/rec_YYYY-MM-DD.csv`** — the filename date is the **decision
Tuesday**. Semicolon-delimited, wide, **German decimals** (`8,9` = 8.9). Header is
`Datum/Volumen` + the 7 calendar days of the planned week (weekends & public holidays
are `0`). Rows, in order:

| Section | Rows | Unit |
|---|---|---|
| Volume forecast | `PAL_Wareneingang` (inbound pallets), `VollPAL_Warenausgang` (outbound full pallets), `Picks_Warenausgang` (picks), `KomPAL_Warenausgang` (picking pallets) | units |
| `Mitarbeiter operativ` | 15 operative activities (Unloading … Aisle maintenance) | person-days |
| `Summe operativ` | sum of the 15 operative rows | person-days |
| `Mitarbeiter administrativ` | 4 admin desks (Control room, Outbound office, Inbound office, Inventory) | person-days |
| `Summe administrativ` | always **8** | person-days |

**`actuals/present_YYYY-MM-DD.csv`** (filename = the planned week's Monday) —
`DATUM` (`DD.MM.YYYY`), **`PRESENT_TOTAL`** = the total person-days *actually present
on the floor that day*, whole-site (operative **+** the constant 8 admin). `FORECAST_PL`
is an empty legacy column. **This is your weekly ground-truth feedback.**

**`actuals/volumes_YYYY-MM-DD.csv`** — `DATUM` (long-form dates, **mixed German and
English** on purpose), `PICKS`, `VOLLPALETTEN`, `KOMMPALETTEN` = the volumes actually
processed (which differ from the forecast the optimiser planned against).

**`clean/present_long.csv`** — `date, present_total_person_days,
present_operative_person_days`. The operative column is simply `present_total − 8`
(admin removed) — **this is the number you are ultimately trying to plan for.**

**`clean/volumes_long.csv`** — both the optimiser's `*_forecast` and the realized
`*_realized` for picks/outbound/inbound, side by side.

### `decision_log.json` — institutional memory, warts and all
The planners' debrief notes, in their own words, with author and date. This is the
human-knowledge channel a compounding system should ingest. **It is unverified and
intentionally inconsistent:** some notes are durable truths, some are hunches that
don't hold up, some were right once and have since gone stale, and at least one pair
**flatly contradicts** each other. Nothing is labelled correct. A note dated
`captured_on` may only inform decisions from that date onward. Deciding *what to
trust, when, and for how long* is a core part of the challenge — not a preprocessing
step.

---

## 3. The timeline (May → October 2026)

24 consecutive weekly cycles. A few things happen along the way; the calendar is real
(German/Baden-Württemberg public holidays close the site), but **the dataset does not
tell you what, when, or how big anything else is.** That's for your system to find.

```
May        Jun        Jul        Aug        Sep        Oct
│──────────│──────────│──────────│──────────│──────────│────────│
 W21                                                    W41   W44
 ├─────────────── 20 TRAINING cycles ──────────────────┤├ HOLDOUT ┤
        (actuals revealed each week)                     (actuals withheld)
```

Public holidays that close the floor (all-zero columns): **25 May** (Whit Monday),
**4 Jun** (Corpus Christi), **3 Oct** (German Unity Day).

---

## 4. The decision you're optimising

For each working day you commit a **staffing plan**. The thing you are really trying to
get right is the **total operative person-days** — staff too few and the work still
has to ship (overtime, temps, late trucks); staff too many and you pay for idle hands.

You can decide at whatever granularity you like (per activity, or just the operative
total). For scoring we look at the **operative total per day**.

---

## 5. How decisions are scored

Decision quality is **money**, using `cost_model.json`. Admin (the constant 8) is
excluded — you always staff it. For each day, against the realized operative need
*N* (= `present_total − 8`):

- **Overstaffing** (planned > N): every surplus person-day is paid but idle →
  **€230 each**.
- **Understaffing** (planned < N): the shortfall is covered at an **+18% overtime
  premium** (€41 each) — *and*, once the daily shortfall exceeds **2.0 person-days**,
  late trucks and missed carrier cut-offs add a **€600 penalty per extra short
  person-day**.

The asymmetry is the lesson in miniature: a *small, deliberate* undershoot is actually
cheaper than playing it safe with a big overshoot — but cut too hard and the SLA
penalty detonates. **Cut toward the truth, not past it.**

**Your score on the held-out weeks** is total cost, reported against two anchors:

| Anchor | What it is |
|---|---|
| **Baseline** | staffing exactly the raw optimiser recommendation — *doing nothing with the data* |
| **Perfect** | staffing exactly the realized need (a floor; day-to-day noise makes it unreachable) |

> *Reference point:* a crude flat "trim everything ~17%" already closes **~86%** of the
> baseline→perfect gap. Getting past that requires the *nuanced* learnings — the easy
> 86% is not where the competition is won. Facilitators score submissions with
> `SOLUTION/scoring.py`; the submission format is `date,planned_operative_person_days`.

---

## 6. What to build (and what we're looking for)

Build **the loop**, not a one-shot forecaster. A strong entry demonstrably:

1. **Captures** why each week's plan diverged from reality — from the actuals *and*
   from the messy decision log.
2. **Applies** those learnings to the next cycle's recommendation, and shows the gap
   shrinking over time.
3. **Curates** its own knowledge: promotes what keeps holding up, and **retires what
   stops being true.**

This maps directly onto the judging criteria:

- **Problem significance** — warehouse staffing is decided this way, every week, at
  thousands of sites. Small per-week percentages are large annual money.
- **Innovation** — the interesting ideas are in *how you represent, trust, and expire
  knowledge*, not in the modelling stack.
- **Functional depth** — there is a real loop here with real feedback and a real score.
  Make something *happen* across cycles; don't stop at a dashboard.

---

## 7. Questions worth asking the data

No spoilers — but here is where the learning is. Treat these as hypotheses to test, and
notice that some will be **dead ends or traps** (which is the point: part of the skill
is finding out *what isn't* true):

- Is the optimiser's error **random, or structured**? Is it the same everywhere, or
  concentrated in particular activities? Does it scale with volume, or have a floor?
- Does the error **stay constant for six months**, or does something **change partway
  through** and make an earlier-correct adjustment wrong?
- Every note in the decision log sounds reasonable. **Do they all actually hold up**
  against the actuals? What do you do when two notes disagree?
- Some patterns **repeat** (and are worth learning); some are **one-offs** (and will
  burn you if you generalise them). Can your system tell which is which *before* the
  holdout?
- The held-out weeks are in **October**. Is October like the rest of the data — or has
  the world moved by then? What would a system that only averages the past get wrong?

A system that can answer these — and, crucially, **knows which of its own answers to
stop trusting** — is exactly the compounding decision engine the track is about.

---

## 8. Ground rules & tips

- **Don't try to reverse-engineer the holdout actuals.** They're withheld; modelling
  the training period honestly is the whole game.
- Day-to-day staffing carries **irreducible noise** — you cannot drive error to zero,
  and chasing the last euro is a sign of overfitting. Aim to *reliably* close the gap.
- Start in `data/clean/`; graduate to the raw files when you want the realism.
- You may use the decision log a lot, a little, or not at all — but the teams that
  combine the **data signal** with the **human signal** tend to learn faster, just as a
  good analyst would.

---

## 9. Provenance & anonymisation

This is **synthetic data**, generated to mirror the *structure and ranges* of a real
3PL warehouse staffing export — weekly optimiser recommendations vs. realized
attendance — but every volume, rate, productivity figure, activity name, site, and date
is invented. No real company, location, product line, or person is represented. It is
safe to share, publish, and keep.
