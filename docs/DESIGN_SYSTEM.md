# DESIGN_SYSTEM.md — paretos Cockpit design language

> **Authoritative source:** the official **paretos Cockpit Design System prompt** (provided by paretos;
> extracted from their React + MUI Cockpit product + Figma Component Library). This SUPERSEDES the
> earlier tokens we reverse-engineered from the paretos.com *marketing* site — the marketing site and
> the **product** are different languages, and we are building a product. Where they conflict, Cockpit
> wins. Implemented in `web/src/theme/`.

## 0. The vibe
A sober operations cockpit: restrained **black / white / grey** shell, with the loud
**magenta→amber brand gradient used sparingly**. The contrast between the calm UI and the rare brand
splash *is* the aesthetic. No hype, no emoji, no marketing fluff in-product. Calm and confident.

## 1. Critical rules (the ones we got wrong before — do not regress)
- **Primary action color is BLACK** (black bg / white text), NOT violet and NOT mint.
- **Sentence case everywhere** (buttons, menus, titles). `text-transform: initial`. No all-caps except
  12px overlines. The wordmark **paretos** is always lowercase.
- **Default radius 7px** (buttons/inputs/cards/dialogs); 10px large cards/accordions; 3px chips; 999px pills.
- **One border weight: 1px solid `#CCCCCC`.** Hover often *strengthens* the border to `#666` rather
  than recoloring — a signature paretos move.
- **Body cards use borders, NOT shadows.** Exactly one shadow exists — `0 0 10px rgba(0,0,0,.15)` — and
  only for floating UI (tooltips, menus, popovers).
- **Violet `#5F26E0`** is for **selection / focus / links / AI CTAs / chart brush** — not general accent.
- Pages **fill width with 40px gutters — never centered with a max-width cap.**
- **No dark mode. No blur. No emoji. No bounce/spring motion. No second typeface beyond mono.**

## 2. Type
- **Aeonik Pro** (Regular 400 / Medium 500) is the only display/text face. Mono = **Consolas**.
- **Our substitute (license-safe, decided):** **Inter** for sans (var `--font-sans`, single swap point to
  Aeonik for a hand-off build), **Consolas/monospace** for `--font-mono` (system font, no webfont).
- Base 16px, body 16/1.25. Headlines default **Medium 500** with **negative letter-spacing** per tier.
  Numerals **tabular by default** in data contexts (`font-variant-numeric: tabular-nums`).
- Overline: 12px, UPPERCASE, 0.6px tracking, `rgba(0,0,0,.4)` (the one uppercase exception).

| Tier | Size | Tracking | Leading |
|---|---|---|---|
| h1 | 44.8px | -0.896px | 1.25 |
| h2 | 38.4px | -0.768px | 1 |
| h3 | 32px | -0.64px | 1 |
| h4 | 25.6px | -0.512px | 1.25 |
| h5 | 19.2px | -0.192px | 1.25 |
| h6 / body1 | 16px | 0 | 1.25 |
| body2 | 14px | — | 1.25 |
| caption | 12px | 0.24px | 1.25 |
| overline | 12px | 0.6px UPPER | 1.25 |

## 3. Color tokens (verbatim)
```css
/* Neutrals — monochrome foundation; black alphas replace tinted greys */
--business-black:    #000000;  /* primary text + primary button */
--business-black-60: #666666;  /* secondary text, strong hover border */
--business-black-40: #999999;  /* tertiary / placeholder */
--business-black-20: #cccccc;  /* THE 1px workhorse border */
--business-black-10: rgba(0,0,0,.10);  /* pressed neutral surface */
--business-black-5:  rgba(0,0,0,.05);  /* disabled surface */
--smokey-silver:     #f2f2f2;  /* universal hover / subtle row surface */
--white:             #ffffff;  /* every surface */

/* Brand accents */
--versatile-violet:  #5f26e0;  /* selection, focus, links, AI CTAs, brush */
--violet-5:  #f7f4fd;  --violet-10: #efe9fc;  --violet-20: #dfd4f9;  /* selected backgrounds */
--popular-pink:      #f500e1;  /* gradient start */
--youthful-yellow:   #fbb03b;  /* warning / gradient end */
--gainful-grey:      #aaa3cc;  /* data slate — chart axes, neutral lavender */

/* Semantic (color + soft bg) */
--generous-green:    #00c04d;  --green-soft:  #e6f9ed;  /* success */
--rebellious-red:    #fb6c4a;  --red-soft:    #fff0ed;  /* error / destructive */
--warning-yellow:    #fbb03b;  --yellow-soft: #fff6e6;  /* warning */
--talkative-turquoise:#51d7e6; --turq-soft:   #e6f9f9;  /* info */

/* Signature gradient — ONLY brand mark, AI CTAs, .gradient-text, loading shimmer */
--brand-gradient: linear-gradient(45.03deg, #f500e1 0%, #fbb03b 100%);
```
**Chart colorway (categorical, in order):** `#9F7DED #96E7F0 #FDA792 #66D994 #FDD089 #999999 #FC896E
#51D7E6 #666666 #33CD71` — soft, desaturated. **Our series mapping:** engine = violet `#5F26E0` (the
hero/selection color), baseline/optimiser = `#999999`, B2 bar = `#9F7DED`, savings = green `#00C04D`,
warning/understaff = yellow `#FBB03B`.

## 4. Spacing / radii / shadow / motion
- **Spacing ladder:** `5 · 10 · 12 · 20 · 30 · 40 · 60 · 80`. Default pad: small 10, med 12, large 20.
  **Page gutters 40px.**
- **Radii:** 3px chips · **7px default** · 10px large cards/accordions · 999px pills.
- **Shadow:** one only `0 0 10px rgba(0,0,0,.15)`, floating UI only.
- **Motion:** subtle/short. Buttons `0.3s` (bg/color/opacity/border), layout `0.2s`, linear/ease-out
  only — no bounce/spring/scroll-scenes. `prefers-reduced-motion` → `0.01ms`.

## 5. Components
- **Button** — height 36px, radius 7px (or 999px `rounded`), sentence case. **Primary = black** bg/white.
  `paretos` variant = brand gradient (AI actions only). Bordered = 1px `#CCC`. Hover: neutral → solid
  `#F2F2F2`; saturated CTA → `opacity .6`. Active: neutral → black-10; saturated → opacity 1. Focus =
  hover look (no separate ring). Disabled: black-5 bg, `rgba(0,0,0,.20)` text.
- **Card** — white, 1px `#CCC` border, **no shadow**, radius 7/10px, pad ~20px.
- **KPI tile** — card + value + delta; pure border-and-text; optional thin colored top accent.
- **Input** — 1px `#CCC`, radius 7px; focus → violet border; error → red border.
- **Chip / badge** — radius 3px; mono labels common.
- **Topbar** — fixed 60px, full-bleed white, hairline bottom border. Logo in a 60×60 square with the
  brand gradient background.
- **Sidebar** — fixed left rail, 60px collapsed / 180px expanded, white, hairline right border, expand
  toggle at bottom. Selected item uses violet (violet-10 bg + violet text/indicator).
- **Content** scrolls; chrome doesn't. Pages fill width, 40px gutters, no max-width cap.

## 6. Icons & imagery
- Line icons, 1px stroke, ~18px, round caps/joins, no fill, recolorable (black default, violet active).
- **Substitute: Lucide at `stroke-width: 1`** in brand color (flagged as a substitution for the in-house set).
- Surfaces pure white — no images/patterns/textures/illustrations. The only "imagery" is data (charts,
  KPI tiles) and the gradient logo. No emoji, no decorative unicode.

## 7. Copy
- Sentence case; confident, direct, mildly technical; no exclamation marks, no hype, no emoji.
- Talk *about* the data ("Target revenue: 35.0 M€"); rarely "you"; never "we" in-app.
- CTAs verb-first ("View title", "Reset zoom"). Empty states = full sentences w/ period. Tooltips short,
  no period. "…" = in-progress. "—" = break. Section headers = short noun phrases ("Overview").

## 8. Implementation
- Tokens in `web/src/theme/tokens.css`; JS mirror for charts in `theme.ts`. **No hex literals in
  component files** — CSS vars only, so the Inter↔Aeonik swap and palette stay single-source.
- `--font-sans` is the only place the family is named.
