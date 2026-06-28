# DECISION_LOG_ANALYSIS.md — Reading the 15 planner notes

> These are **claims, not facts** (README §2). Each must be validated against actuals in a
> **walk-forward** way: a note `captured_on` date D may only influence decisions made on/after D.
> This file is my *prior* reading; the engine must **verify each claim empirically** and assign a
> trust weight + expiry. Do NOT hardcode these as truths — that is reward hacking (see
> ANTI_REWARD_HACKING.md). The columns below are hypotheses to test, not answers.

## Claim table
| ID | Date | Author | Scope | Claim (machine hint) | My prior read — VERIFY before trusting |
|----|------|--------|-------|----------------------|----------------------------------------|
| L01 | 05-19 | Maya | transit | Transit drivers = fixed 4, ignore optimiser scaling | Plausible "fixed cell". Test: variance of realized transit ≈ 0? |
| L02 | 06-02 | Maya | co_packing | Co-Packing = hard 4 | Plausible fixed cell. Pairs with L10. |
| L03 | 06-09 | Jonas | picking | Trim picking −12% | **STALE after ~08-24** — superseded by L11/L12 (pick-by-light). Valid only Jun–Aug. |
| L04 | 06-16 | Maya | receiving | +1 Receiving on Mondays | Weekday rule. Test Monday receiving residual. |
| L05 | 06-23 | Selin | loading | +1 Loading on payday-Mondays ("to be safe") | **Suspect** — hedge language, n is tiny. Likely a TRAP/noise. Verify hard. |
| L06 | 06-30 | Jonas | picking | −1 picker when picks < 7000 | Conditional. Test low-volume days only. |
| L07 | 07-07 | Maya | receiving,putaway | +1 each on day-after-closure | Few closures in data (3). Low n; check the day-after each holiday. |
| L08 | 07-21 | Selin | operative | Cut whole operative −15% in W30–W33 (late summer) | **CONTRADICTS L09.** One of L08/L09 is wrong (or both partly). |
| L09 | 07-28 | Jonas | operative | Heat KILLS throughput, needed MORE not fewer; don't cut | **CONTRADICTS L08.** Resolve empirically: did W30–W33 need rise or fall? |
| L10 | 08-11 | Maya | co_packing | Co-Packing fixed-4 held 8 weeks; apply blindly | Reaffirms L02. "Apply blindly" = curation risk; still verify it didn't drift. |
| L11 | 08-25 | Maya | picking | Pick-by-light live 08-24; picking now −25% | **REGIME CHANGE.** Key event. Supersedes L03 from 08-24. |
| L12 | 09-01 | Jonas | picking | Confirm −25–30%; **retire the old 12%** | Confirms L11; explicit **retire** signal for L03. Use −27% from 08-24. |
| L13 | 09-15 | Selin | vna_replen | +1 VNA when inbound > 2000 ("saw it twice") | Low n ("twice"). Conditional. Verify; may be noise. |
| L14 | 09-22 | Maya | staging,loading | Autumn ramp; outbound climbing; plan AHEAD of forecast | **Trend note** — matters for the Oct holdout. No fixed number. |
| L15 | 09-29 | Jonas | operative | Autumn ramp confirmed, picks +8% MoM, staff to the trend | **Holdout-relevant trend.** Plan above rear-view average for October. |

## The structural lessons the log encodes (the "compounding" narrative)
1. **Fixed cells** (L01 transit, L02/L10 co-packing): optimiser scales them with volume but they
   don't move. Easy, durable win if verified.
2. **A durable scale error** (L03 picking −12%) that later **goes stale** (L11/L12) due to a
   **regime change** (pick-by-light, 2026-08-24). A compounding system must *retire* L03 and adopt
   the new number from the event date — the headline test of "expire stale knowledge."
3. **A genuine contradiction** (L08 vs L09) the system must resolve from data, not vibes.
4. **Conditional/weekday micro-rules** (L04, L06, L07, L13) — small, possibly real, possibly noise.
   Each needs an honest significance test; some are deliberate **traps** (README §7).
5. **A forward-looking trend** (L14/L15) that a backward-looking average will *underplan* in the
   October holdout — the README §7 hint that "October may not be like the rest."

## Cross-references to events the data should reveal (test, don't assume)
- **Pick-by-light go-live ≈ 2026-08-24** → picking error jumps from ~−12% to ~−25/30%.
- **Autumn/flu ramp from ~mid/late-Sep** → outbound roles (staging, loading) trend up into October.
- **Late-summer (W30–W33, ~late Jul)** → L08/L09 dispute; resolve with realized need vs forecast.
