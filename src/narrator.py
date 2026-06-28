"""(B) Natural-language explanation of an already-verified decision trace.

The narrator ONLY rephrases numbers the engine already computed (recommendation, trim factor k,
regime boundary, trend lead, final plan, and — on training days — the actual and cost). It invents
no numbers and makes no decisions, so there is no hallucination risk to the staffing plan: at worst
the prose is awkward, never wrong about the math.

With no ANTHROPIC_API_KEY, `explain` returns None and the API falls back to the deterministic
template reason (AppState._reason). Same facts, plainer phrasing.
"""
from __future__ import annotations

from typing import Dict, Optional

from . import llm

_SYSTEM = (
    "You explain a warehouse shift planner's staffing decision in 2-3 plain sentences. Use ONLY the "
    "numbers given — never invent or recompute. Audience: a shift planner who wants to trust the number, "
    "not a data scientist. No jargon (avoid 'regime', 'coefficient'); say things like 'recent weeks ran "
    "under plan' instead. Lead with the recommended number."
)


def explain_plan(trace: Dict) -> Optional[str]:
    """Plain-English 'why this number' for the Normal-mode planner, from a verified trace dict."""
    t = trace
    facts = [
        f"- optimiser suggested: {t['recommended']} person-days",
        f"- we plan: {t['planned']} person-days (trim factor {t['k']})",
    ]
    if t.get("regime_boundary"):
        facts.append(f"- a process change on {t['regime_boundary']} (pick-by-light) sped up picking; "
                     f"we only use data since then")
    if t.get("trend_adj"):
        facts.append(f"- demand trend adjustment: {t['trend_adj']:+.1f} person-days")
    if t.get("actual") is not None:
        facts.append(f"- what was actually needed that day: {t['actual']} (this is a past, checked day)")
    prompt = ("Explain this staffing decision for " + t["date"] + ":\n" + "\n".join(facts))
    return llm.narrate(prompt, system=_SYSTEM)


def answer_question(question: str, trace: Dict, summary: Dict) -> Optional[str]:
    """Advanced-mode 'ask why' — answer a question grounded ONLY in the verified trace + summary."""
    ctx = {
        "date": trace.get("date"), "recommended": trace.get("recommended"),
        "planned": trace.get("planned"), "trim_factor_k": trace.get("k"),
        "regime_boundary": trace.get("regime_boundary"), "trend_adj": trace.get("trend_adj"),
        "actual_needed": trace.get("actual"), "our_cost": trace.get("our_cost"),
        "baseline_cost": trace.get("baseline_cost"),
        "overall_gap_closed_pct": summary.get("engine_gap_closed_pct"),
        "overall_saving_eur": summary.get("saving_vs_baseline_eur"),
    }
    prompt = (
        "Answer the user's question using ONLY these verified facts (do not invent numbers; if the "
        "facts don't cover it, say so):\n"
        + "\n".join(f"- {k}: {v}" for k, v in ctx.items() if v is not None)
        + f"\n\nQuestion: {question}"
    )
    return llm.narrate(prompt, system=(
        "You answer questions about a specific staffing decision using only the provided verified "
        "numbers. Be concrete and honest; never fabricate figures."), max_tokens=400)
