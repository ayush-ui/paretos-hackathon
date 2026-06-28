"""AppState — precompute-and-cache layer between the engine and the HTTP API.

On construction it runs the cheap, always-needed pieces (curate graph, backtest, holdout plan).
The expensive pieces (the 20-week live compounding loop, the validation sweep, per-week as-of graph
snapshots) are computed lazily on first request and cached. This keeps startup fast while making
every endpoint instant after warm-up.

Engine config is fixed here (the validated Phase-4 settings); the API is read-only over it.
"""
from __future__ import annotations

import datetime as _dt
from functools import lru_cache
from typing import Dict, List, Optional

from src import data, curate, predict, llm, narrator
from src.cost import day_cost, gap_closed_pct, cost_breakdown
from eval.backtest import (Context, run, make_ew_ratio, make_flat_trim, strat_baseline,
                           _decision_week_monday)

ENGINE_CFG = dict(halflife=21.0, offset=0.3, trend_gain=0.4)
HOLDOUT_DECISIONS = ("2026-09-29", "2026-10-06", "2026-10-13", "2026-10-20")


class AppState:
    def __init__(self):
        self.present = data.load_present()
        self.recs = data.load_recommendations()
        self.volumes = data.load_volumes()
        self.rec_op_by_date = {d: t for r in self.recs.values()
                               for d, t in r.operative_totals().items() if data.is_working_day(d)}

        # End-state curated graph + engine (the canonical, all-training view).
        self.graph = curate.build_graph()
        curate.curate(self.graph, self.present, self.recs)
        self.engine = predict.Engine(self.graph, **ENGINE_CFG)

        # Baselines + engine backtest (fast).
        self._bt_engine = run(self.engine.as_strategy())
        self._bt_b0 = run(strat_baseline)
        self._bt_b1 = run(make_flat_trim(0.83))
        self._bt_b2 = run(make_ew_ratio(14))

        # Re-hydrate any planner notes captured in earlier sessions into the live graph.
        self._load_planner_notes()

        # Persist the end-state belief-graph snapshot behind the swappable persistence adapter
        # (file-backed under state/ now; Postgres/Neon later — one-adapter swap). Best-effort:
        # a write failure must never break the read-only engine.
        self._persist_graph_snapshot()

    def _persist_graph_snapshot(self) -> None:
        # Lightweight structural snapshot (no expensive € contributions) — enough to rehydrate the
        # graph offline and to show what knowledge existed at boot.
        try:
            from src.persistence import get_persistence
            nodes = [{"id": b.id, "kind": b.kind, "status": b.status, "trust": round(b.trust, 2),
                      "scope": ", ".join(b.activities) or "operative", "valid_from": b.valid_from,
                      "valid_to": b.valid_to, "author": b.author, "note": b.note}
                     for b in self.graph.list()]
            edges = [{"src": e.src, "dst": e.dst, "kind": e.kind} for e in self.graph.edges]
            get_persistence().save("graph_snapshot",
                                   {"saved_at": _dt.datetime.now().isoformat(timespec="seconds"),
                                    "nodes": nodes, "edges": edges})
        except Exception:
            pass

    # --- helpers --------------------------------------------------------------------------
    def _ctx(self, decision_date: str) -> Context:
        return Context(self.present, self.volumes, self.rec_op_by_date, _decision_week_monday(decision_date))

    def _decision_for_date(self, date: str) -> Optional[str]:
        """Which decision cycle's planned week contains `date`?"""
        for dd, rec in self.recs.items():
            if date in rec.dates:
                return dd
        return None

    # --- summary --------------------------------------------------------------------------
    def summary(self) -> Dict:
        e, b0, b2 = self._bt_engine, self._bt_b0, self._bt_b2
        return {
            "n_days": e["n_days"],
            "baseline_cost": round(b0["total_baseline_cost"]),
            "engine_cost": round(e["total_strategy_cost"]),
            "b1_flat_cost": round(self._bt_b1["total_strategy_cost"]),
            "b2_adaptive_cost": round(b2["total_strategy_cost"]),
            "engine_gap_closed_pct": round(e["gap_closed_pct"], 2),
            "b2_gap_closed_pct": round(b2["gap_closed_pct"], 2),
            "saving_vs_baseline_eur": round(b0["total_baseline_cost"] - e["total_strategy_cost"]),
            "breakdown": {k: round(v) for k, v in e["breakdown"].items()},
        }

    # --- cycles ---------------------------------------------------------------------------
    def cycles(self) -> List[Dict]:
        return [{"decision_date": r["decision_date"], "days": r["days"],
                 "engine_cost": round(r["strategy_cost"]),
                 "baseline_cost": round(r["baseline_cost"]),
                 "gap_closed_pct": round(r["gap_closed_pct"], 1)}
                for r in self._bt_engine["rows"]]

    # --- plan (current = holdout) ---------------------------------------------------------
    def current_plan(self) -> List[Dict]:
        from api.absences import get_store, coverage_for_day
        absences_by_date = get_store().open_count_by_date()
        rows = []
        for dd in HOLDOUT_DECISIONS:
            rec = self.recs[dd]
            ctx = self._ctx(dd)
            days = [d for d in rec.dates if data.is_working_day(d)]
            plan = self.engine.plan_cycle(rec, days, ctx)
            # Confidence is derived once per decision cycle: within a planned week the trailing regime
            # history (info horizon = decision Monday) is identical, so its stability is shared.
            conf_level, conf_basis = self._cycle_confidence(rec, days, ctx)
            for d in sorted(plan):
                recd = rec.operative_total(d)
                target = round(plan[d])
                # live coverage: absences (from Discord) lower confirmed below target → € risk.
                cov = coverage_for_day(target, absences_by_date.get(d, 0))
                rows.append({
                    "date": d,
                    "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][data.weekday(d)],
                    "decision_date": dd,
                    "planned": round(plan[d], 2),
                    "recommended": round(recd, 2),
                    # --- product translation layer (1 person-day = 1 person on 1 shift/day) ---
                    "target_headcount": target,
                    "optimiser_headcount": round(recd),
                    "confirmed_headcount": cov["confirmed_headcount"],
                    "coverage": cov["coverage"],
                    "short_by": cov["short_by"],
                    "sla_risk_eur": cov["sla_risk_eur"],
                    "confidence": conf_level,
                    "confidence_basis": conf_basis,
                    "reason_short": self._reason_short(recd, plan[d]),
                    # estimated idle cost avoided by trimming (the optimiser reliably overstaffs at
                    # ~€230/idle person-day); true realised € is unknowable without actuals.
                    "est_saving_eur": round((recd - plan[d]) * 230),
                    "trim_pct": round(100 * (1 - plan[d] / recd), 1) if recd else 0.0,
                })
        return rows

    def absence_impact(self, absence: Dict) -> Dict:
        """Coverage impact of one absence on its day: target, confirmed-after, € risk, recommendation,
        and a human line the bot echoes to Discord. Grounded in the real asymmetric cost model."""
        from api.absences import get_store, coverage_for_day
        from src.cost import SLA_TOLERANCE_PERSON_DAYS
        date = absence["date"]
        row = next((r for r in self.current_plan() if r["date"] == date), None)
        target = row["target_headcount"] if row else 0
        eff_absences = get_store().open_count_by_date().get(date, 0)
        cov = coverage_for_day(target, eff_absences)
        short = cov["short_by"]
        sla_breach = short > SLA_TOLERANCE_PERSON_DAYS
        weekday = row["weekday"] if row else ""
        if not row:
            rec = "This date isn't in the current plan window, so there's no staffing impact."
            msg = f"Logged {absence['worker']}'s absence on {date}, but it falls outside the planned weeks."
        elif sla_breach:
            rec = (f"Fill the gap: {short} short risks an SLA breach (~€{cov['sla_risk_eur']}). "
                   f"Call in standby/overtime — cheaper than the penalty.")
            msg = (f"⚠️ {weekday} {date} is now {short} short of {target}. "
                   f"SLA-breach risk ~€{cov['sla_risk_eur']}. Planner has been alerted to resolve.")
        elif short:
            rec = (f"Within the 2.0 tolerance ({short} short). Fill if convenient (~€{cov['sla_risk_eur']} "
                   f"overtime risk), or accept the small gap.")
            msg = (f"{weekday} {date} is now {short} short of {target} (within tolerance, "
                   f"~€{cov['sla_risk_eur']} risk). Logged for the planner.")
        else:
            rec = "No shortfall."
            msg = f"Logged {absence['worker']}'s absence on {weekday} {date}."
        return {
            "absence": absence, "date": date, "weekday": weekday,
            "target_headcount": target, "confirmed_headcount": cov["confirmed_headcount"],
            "short_by": short, "sla_risk_eur": cov["sla_risk_eur"], "sla_breach": sla_breach,
            "recommendation": rec, "message": msg,
        }

    # --- planner notes (human-in-the-loop knowledge capture) ------------------------------
    def _today(self) -> str:
        return _dt.date.today().isoformat()

    def _load_planner_notes(self) -> None:
        from api import notes
        for rec in notes.get_store().list():
            try:
                b = notes.build_belief(rec["raw_text"], rec.get("author"), rec["captured_on"],
                                       rec["id"], rec.get("parsed"))
                self.graph.add(b)
            except Exception:
                continue

    def note_preview(self, text: str, author: Optional[str]) -> Dict:
        from api import notes
        return notes.interpret(text, author, self._today(), notes.get_store().next_id())

    def note_commit(self, text: str, author: Optional[str], parsed: Optional[Dict]) -> Dict:
        from api import notes
        store = notes.get_store()
        note_id = store.next_id()
        captured_on = self._today()
        b = notes.build_belief(text, author, captured_on, note_id, parsed)
        self.graph.add(b)
        store.add({"id": note_id, "raw_text": text, "author": author,
                   "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
                   "captured_on": captured_on, "parsed": parsed})
        self.graph_snapshot.cache_clear()  # so GET /api/graph reflects the new node
        return self._belief_dict(b, 0.0)

    def note_delete(self, note_id: str) -> bool:
        from api import notes
        if not notes.get_store().delete(note_id):
            return False
        self.graph.beliefs.pop(note_id, None)
        self.graph_snapshot.cache_clear()
        return True

    def plan_dates(self) -> List[Dict]:
        """Lightweight {date, weekday} list of plannable days — for the bot to map free-text to a date."""
        out = []
        for dd in HOLDOUT_DECISIONS:
            for d in sorted(x for x in self.recs[dd].dates if data.is_working_day(x)):
                out.append({"date": d,
                            "weekday": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][data.weekday(d)]})
        return out

    def _cycle_confidence(self, rec, days, ctx) -> tuple:
        """Honest confidence from the stability of the recent regime ratios. October is a forecast
        beyond observed data, so holdout cycles are capped at 'medium' (see PROGRESS HOLDOUT RISK)."""
        import statistics
        ex = self.engine.explain(rec, days[0], ctx)
        ratios = list(ex.get("history_ratios", {}).values())
        is_holdout = self.present.get(days[0]) is None
        if len(ratios) < 3:
            return ("medium", "Limited recent history to calibrate the trim.")
        cv = statistics.pstdev(ratios) / statistics.mean(ratios)
        if cv < 0.02:
            level, basis = "high", "Recent weeks ran at a very steady ratio to the optimiser."
        elif cv < 0.035:
            level, basis = "medium", "Recent weeks ran at a fairly steady ratio to the optimiser."
        else:
            level, basis = "low", "Recent weeks were volatile, so the trim is less certain."
        if is_holdout and level == "high":
            level = "medium"
            basis += " Capped: October is a forecast beyond observed data."
        return (level, basis)

    @staticmethod
    def _reason_short(recommended: float, planned: float) -> str:
        trim = round(100 * (1 - planned / recommended)) if recommended else 0
        return (f"Optimiser says {recommended:.0f}; recent weeks ran ~{trim:.0f}% under, "
                f"so we staff {planned:.0f}.")

    # --- trace ----------------------------------------------------------------------------
    def trace(self, date: str) -> Optional[Dict]:
        dd = self._decision_for_date(date)
        if dd is None:
            return None
        rec = self.recs[dd]
        ctx = self._ctx(dd)
        ex = self.engine.explain(rec, date, ctx)
        # attach outcome if this is a training day with known actuals
        actual = self.present.get(date)
        if actual is not None:
            ex["actual"] = round(actual, 2)
            ex["our_cost"] = round(day_cost(ex["planned"], actual), 1)
            ex["baseline_cost"] = round(day_cost(ex["recommended"], actual), 1)
        ex["is_holdout"] = actual is None
        ex["reason_text"] = self._reason(ex)
        return ex

    # --- LLM (optional) -------------------------------------------------------------------
    def llm_status(self) -> Dict:
        return {"available": llm.available(), "model": llm.MODEL}

    def explain(self, date: str) -> Optional[Dict]:
        """Natural-language explanation of a day's plan. Uses the LLM if configured, else the
        deterministic template — same verified facts either way."""
        t = self.trace(date)
        if t is None:
            return None
        text = narrator.explain_plan(t)
        return {"date": date, "text": text or t["reason_text"], "llm_used": text is not None}

    def ask(self, date: str, question: str) -> Optional[Dict]:
        t = self.trace(date)
        if t is None:
            return None
        ans = narrator.answer_question(question, t, self.summary())
        if ans is None:
            ans = ("LLM Q&A is not configured. Set ANTHROPIC_API_KEY to enable it. "
                   f"Deterministic summary: {t['reason_text']}")
            return {"date": date, "question": question, "answer": ans, "llm_used": False}
        return {"date": date, "question": question, "answer": ans, "llm_used": True}

    def _reason(self, ex: Dict) -> str:
        trim = round(100 * (1 - ex["k"]), 0)
        bits = [f"Optimiser suggested {ex['recommended']:.0f}; recent weeks ran ~{trim:.0f}% under, "
                f"so we trim to {ex['level']:.0f}."]
        if ex["regime_boundary"]:
            bits.append(f"Using the post-{ex['regime_boundary']} regime (pick-by-light) history only.")
        if ex["trend_adj"] and abs(ex["trend_adj"]) >= 0.05:
            bits.append(f"Demand is trending up, so +{ex['trend_adj']:.1f} lead.")
        bits.append(f"Final plan: {ex['planned']:.0f} person-days.")
        return " ".join(bits)

    # --- belief graph (cached per as_of) --------------------------------------------------
    @lru_cache(maxsize=64)
    def graph_snapshot(self, as_of: Optional[str] = None) -> Dict:
        if as_of is None:
            g = self.graph
        else:
            g = curate.build_graph()
            curate.curate(g, self.present, self.recs, as_of=as_of)
        contrib = self._belief_contributions()
        known = [b for b in g.list() if as_of is None or b.valid_from < as_of]
        known_ids = {b.id for b in known}
        nodes = [self._belief_dict(b, contrib.get(b.id, 0.0)) for b in known]
        edges = [{"src": e.src, "dst": e.dst, "kind": e.kind}
                 for e in g.edges if e.src in known_ids and e.dst in known_ids]
        return {"as_of": as_of, "nodes": nodes, "edges": edges}

    def _belief_dict(self, b, contribution: float) -> Dict:
        return {
            "id": b.id, "kind": b.kind, "status": b.status, "trust": round(b.trust, 2),
            "activities": b.activities, "scope": ", ".join(b.activities) or "operative",
            "valid_from": b.valid_from, "valid_to": b.valid_to, "author": b.author,
            "note": b.note, "contribution_eur": round(contribution),
            "evidence": list(b.evidence),
        }

    def belief(self, belief_id: str) -> Optional[Dict]:
        b = self.graph.beliefs.get(belief_id)
        if b is None:
            return None
        return self._belief_dict(b, self._belief_contributions().get(belief_id, 0.0))

    @lru_cache(maxsize=1)
    def _belief_contributions(self) -> Dict[str, float]:
        """€ each non-retired belief is worth (cost_without - cost_with), end-state engine."""
        full = self._bt_engine["total_strategy_cost"]
        out: Dict[str, float] = {}
        for b in self.graph.list():
            if b.status == "retired":
                out[b.id] = 0.0
                continue
            saved = b.status
            b.status = "retired"
            without = run(predict.Engine(self.graph, **ENGINE_CFG).as_strategy())["total_strategy_cost"]
            b.status = saved
            out[b.id] = without - full
        return out

    # --- provenance KG (Decision/Outcome/Source ontology, cached) -------------------------
    @lru_cache(maxsize=1)
    def _provenance(self):
        """Full walk-forward provenance graph (built once; as_of views filter this in-memory)."""
        from src.provenance import build_provenance
        return build_provenance(present=self.present, recs=self.recs, volumes=self.volumes,
                                **ENGINE_CFG)

    def provenance(self, as_of: Optional[str] = None) -> Dict:
        """JSON the React Flow cockpit consumes: Source/Belief/Decision/Outcome nodes + provenance
        edges. `as_of` trims to weeks decided strictly before that date (honest time-travel)."""
        pg = self._provenance()
        snap = pg.snapshot()
        if as_of is None:
            return snap
        keep_weeks = {n["id"] for n in snap["nodes"]
                      if n["type"] in ("decision", "outcome") and n.get("week", "9999") < as_of}
        # keep beliefs/sources captured before as_of, plus the in-window decision/outcome nodes
        nodes = [n for n in snap["nodes"]
                 if (n["type"] in ("decision", "outcome") and n["id"] in keep_weeks)
                 or (n["type"] == "belief" and n.get("valid_from", "9999") < as_of)
                 or n["type"] == "source"]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in snap["edges"] if e["src"] in node_ids and e["dst"] in node_ids]
        counts: Dict[str, int] = {}
        for n in nodes:
            counts[n["type"]] = counts.get(n["type"], 0) + 1
        return {"as_of": as_of, "nodes": nodes, "edges": edges, "counts": counts}

    def provenance_trace(self, week: str) -> Optional[Dict]:
        """Trace one decision week back to the beliefs+notes that informed it and its € outcome."""
        pg = self._provenance()
        if f"decision:{week}" not in pg.nodes:
            return None
        return pg.trace(week)

    # --- shadow-trust trajectory (observability, cached) ----------------------------------
    @lru_cache(maxsize=1)
    def trust_trajectory(self) -> Dict:
        """Week-by-week EWMA trust curve per belief (shadow of, not a replacement for, curation)."""
        from src.trust_trajectory import build_trajectories
        return build_trajectories(present=self.present, recs=self.recs, volumes=self.volumes,
                                  **ENGINE_CFG)

    # --- staffing person-days over time (cached) ------------------------------------------
    @lru_cache(maxsize=1)
    def staffing_series(self) -> List[Dict]:
        """Per decision-week total operative person-days: our plan vs the optimiser vs the realized
        actual. Walk-forward (each week planned at its own horizon); holdout weeks omit the actual.
        Same engine/numbers as the headline backtest."""
        out = []
        for dd in sorted(self.recs):
            rec = self.recs[dd]
            days = [d for d in rec.dates if data.is_working_day(d)]
            if not days:
                continue
            ctx = self._ctx(dd)
            plan = self.engine.plan_cycle(rec, days, ctx)
            actuals = [self.present[d] for d in days if d in self.present]
            is_holdout = len(actuals) == 0
            out.append({
                "week": dd,
                "label": dd[5:],
                "planned_pd": round(sum(plan.values()), 1),
                "optimiser_pd": round(sum(rec.operative_total(d) for d in days), 1),
                "actual_pd": round(sum(actuals), 1) if not is_holdout else None,
                "is_holdout": is_holdout,
            })
        return out

    # --- synthetic stress-test (cached) ---------------------------------------------------
    @lru_cache(maxsize=1)
    def synthetic_stress(self) -> Dict:
        """Robustness across SYNTHETIC regime worlds (frozen engine vs no-knowledge ablation).
        Labelled synthetic; the real-data ablation (validation endpoint) is the primary evidence."""
        from eval.synthetic_stress import run_all
        rows = run_all()
        for r in rows:
            r.pop("provenance", None)  # keep the payload light; provenance text is in the eval script
        return {"worlds": rows,
                "note": ("SYNTHETIC stress-test — alternative Octobers the single real holdout can't "
                         "show. 'Ablation' = our engine minus the belief graph + trend lead; the engine "
                         "should win where the regime is learnable (ramp, pick-by-light). The real-data "
                         "ablation remains the primary evidence.")}

    # --- compounding (cached) -------------------------------------------------------------
    @lru_cache(maxsize=1)
    def compounding(self) -> List[Dict]:
        from eval.compounding import run_live, _WATCH
        timeline, _, _ = run_live(verbose=False, **{k: ENGINE_CFG[k] for k in ENGINE_CFG})
        out, cum_p, cum_b = [], 0.0, 0.0
        for dd, statuses, cyc_cost, cyc_base in timeline:
            cum_p += cyc_cost; cum_b += cyc_base
            out.append({"decision_date": dd, "statuses": statuses,
                        "cycle_cost": round(cyc_cost), "cycle_baseline": round(cyc_base),
                        "cum_gap_pct": round(gap_closed_pct(cum_p, cum_b), 1)})
        return out

    # --- validation (cached) --------------------------------------------------------------
    @lru_cache(maxsize=1)
    def validation(self) -> Dict:
        import statistics
        contrib = self._belief_contributions()
        ablation = sorted(
            [{"id": bid, "contribution_eur": round(v)} for bid, v in contrib.items()],
            key=lambda r: -r["contribution_eur"])
        costs = []
        for hl in (14, 21, 28, 35):
            for off in (0.0, 0.3, 0.6):
                for tg in (0.0, 0.4, 0.8):
                    costs.append(run(predict.Engine(self.graph, halflife=hl, offset=off,
                                                    trend_gain=tg).as_strategy())["total_strategy_cost"])
        b2 = self._bt_b2["total_strategy_cost"]
        # noise floor: oracle 2-regime mean-ratio plan
        days = sorted(d for d in self.present if data.is_working_day(d) and d in self.rec_op_by_date)
        pre = [self.present[d] / self.rec_op_by_date[d] for d in days if d < "2026-08-25"]
        post = [self.present[d] / self.rec_op_by_date[d] for d in days if d >= "2026-08-25"]
        floor = sum(day_cost(self.rec_op_by_date[d] *
                             (statistics.mean(pre) if d < "2026-08-25" else statistics.mean(post)),
                             self.present[d]) for d in days)
        return {
            "ablation": ablation,
            "sensitivity": {"n_configs": len(costs), "min": round(min(costs)),
                            "median": round(statistics.median(costs)), "max": round(max(costs)),
                            "configs_beating_b2": sum(1 for c in costs if c < b2), "b2_cost": round(b2)},
            "noise_floor": {"oracle_2regime_cost": round(floor),
                            "engine_cost": round(self._bt_engine["total_strategy_cost"]),
                            "pre_regime_mean_ratio": round(statistics.mean(pre), 3),
                            "post_regime_mean_ratio": round(statistics.mean(post), 3)},
        }


_STATE: Optional[AppState] = None


def get_state() -> AppState:
    global _STATE
    if _STATE is None:
        _STATE = AppState()
    return _STATE
