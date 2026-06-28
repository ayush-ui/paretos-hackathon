"""Provenance knowledge-graph — the audit trail a supply-chain jury wants.

The belief graph (src/beliefs.py) stores WHAT we believe. This layer stores the WHY and the
CONSEQUENCE: it walks the decisions forward week by week and records, as a typed graph,

    Source  --(belief came from)-->  Belief  --INFORMED-->  Decision
    Decision --RESULTED_IN--> Outcome --UPDATED--> Belief (trust moved by what reality cost)
    Decision --PRECEDED--> Decision (the week-to-week timeline)

so you can TRACE a staffing number back through the belief that shaped it, the planner note that
seeded that belief, the € the decision actually cost, and the trust update that fed the next week.
That chain — plan -> belief -> note -> € outcome -> trust update -> next week — is the compounding.

Ontology (node types): Source | Belief | Decision | Outcome.
Edge types: SOURCED_FROM | INFORMED | CONSIDERED | RESULTED_IN | UPDATED | PRECEDED | CONTRADICTS.

In-process only (plain dict/list structures — no Neo4j, no networkx dependency). Built walk-forward:
each Decision is curated with `as_of` = its own decision-week Monday, so a node never depends on an
actual it could not have known (ANTI_REWARD_HACKING.md). Idea ported from the teammate's engine/kg.py;
re-implemented on our data + cost so it shares the scored engine's numbers exactly.
"""
from __future__ import annotations

import datetime as _dt
from typing import Dict, List, Optional

from . import data, curate, predict
from .cost import score_plan, gap_closed_pct, day_cost
from eval.backtest import Context


def _monday(decision_date: str) -> str:
    d = _dt.date.fromisoformat(decision_date)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def _source_of(belief) -> str:
    """Where the belief came from: a named planner note vs the decision log vs derived data."""
    if belief.author:
        return f"planner:{belief.author}"
    if belief.source == "derived":
        return "data:change-detection"
    return "log:decision-log"


class ProvenanceGraph:
    """A small typed graph of Source/Belief/Decision/Outcome nodes + provenance edges.

    Plain in-memory lists keyed by id; `snapshot()` emits the JSON the React Flow cockpit consumes.
    """

    def __init__(self):
        self.nodes: Dict[str, Dict] = {}
        self.edges: List[Dict] = []

    # --- node/edge builders ---------------------------------------------------------------
    def _node(self, nid: str, ntype: str, **attrs) -> str:
        if nid not in self.nodes:
            self.nodes[nid] = {"id": nid, "type": ntype, **attrs}
        else:
            self.nodes[nid].update(attrs)
        return nid

    def _edge(self, src: str, dst: str, etype: str, **attrs) -> None:
        self.edges.append({"src": src, "dst": dst, "type": etype, **attrs})

    def add_source(self, key: str, label: str) -> str:
        return self._node(f"source:{key}", "source", label=label)

    def add_belief(self, b, source_key: str) -> str:
        nid = self._node(f"belief:{b.id}", "belief", label=b.id, status=b.status,
                         trust=round(b.trust, 2), kind=b.kind,
                         scope=", ".join(b.activities) or "operative",
                         note=b.note, valid_from=b.valid_from, valid_to=b.valid_to)
        src = self.add_source(source_key, _source_label(source_key, b))
        # de-duplicate the SOURCED_FROM edge
        if not any(e["src"] == nid and e["dst"] == src and e["type"] == "SOURCED_FROM"
                   for e in self.edges):
            self._edge(nid, src, "SOURCED_FROM")
        return nid

    def add_decision(self, week: str, plan_total: float, k: float, n_days: int) -> str:
        return self._node(f"decision:{week}", "decision", label=f"Week of {week}",
                          week=week, plan_total=round(plan_total, 1), k=round(k, 4), n_days=n_days)

    def add_outcome(self, week: str, cost: float, baseline_cost: float,
                    is_forecast: bool) -> str:
        gap = gap_closed_pct(cost, baseline_cost) if baseline_cost else 0.0
        # hue in [0,1]: 1 = closed the whole gap (green), 0 = no better than baseline (red)
        hue = max(0.0, min(1.0, gap / 100.0))
        return self._node(f"outcome:{week}", "outcome", label=f"Outcome {week}",
                          week=week, cost=round(cost), baseline_cost=round(baseline_cost),
                          gap_closed_pct=round(gap, 1), hue=round(hue, 3), is_forecast=is_forecast)

    def informed(self, belief_id: str, week: str, material: bool) -> None:
        etype = "INFORMED" if material else "CONSIDERED"
        self._edge(f"belief:{belief_id}", f"decision:{week}", etype)

    def resulted_in(self, week: str) -> None:
        self._edge(f"decision:{week}", f"outcome:{week}", "RESULTED_IN")

    def preceded(self, prev_week: str, week: str) -> None:
        self._edge(f"decision:{prev_week}", f"decision:{week}", "PRECEDED")

    def updated(self, week: str, belief_id: str, delta: float) -> None:
        self._edge(f"outcome:{week}", f"belief:{belief_id}", "UPDATED", delta=round(delta, 4))

    def contradicts(self, a: str, b: str) -> None:
        self._edge(f"belief:{a}", f"belief:{b}", "CONTRADICTS")

    # --- reading --------------------------------------------------------------------------
    def snapshot(self) -> Dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges,
                "counts": self.counts()}

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for n in self.nodes.values():
            out[n["type"]] = out.get(n["type"], 0) + 1
        return out

    def trace(self, week: str) -> Dict:
        """Trace one decision back to the beliefs + sources that informed it, and forward to its
        outcome — the plan -> belief -> note -> € chain, for a single week."""
        dnode = f"decision:{week}"
        beliefs_in = []
        for e in self.edges:
            if e["dst"] == dnode and e["type"] in ("INFORMED", "CONSIDERED"):
                bnode = self.nodes.get(e["src"], {})
                src = next((self.nodes[x["dst"]]["label"] for x in self.edges
                            if x["src"] == e["src"] and x["type"] == "SOURCED_FROM"), None)
                beliefs_in.append({"belief": bnode.get("label"), "trust": bnode.get("trust"),
                                   "scope": bnode.get("scope"), "note": bnode.get("note"),
                                   "role": e["type"], "source": src})
        beliefs_in.sort(key=lambda x: (x["role"] != "INFORMED", -(x["trust"] or 0)))
        outcome = self.nodes.get(f"outcome:{week}")
        return {"week": week, "decision": self.nodes.get(dnode),
                "informed_by": beliefs_in, "outcome": outcome}


def _source_label(source_key: str, b) -> str:
    if source_key.startswith("planner:"):
        return f"Planner note ({b.author})"
    if source_key.startswith("data:"):
        return "Data (change-detection)"
    return "Decision log"


def _materially_informs(b, scored_days: List[str], decision_date: str,
                        boundaries: List[str], trend_active: bool) -> bool:
    """Did this belief actually shape the engine's plan for this week (vs merely being eligible)?

    Material drivers of the engine output: a non-retired regime-boundary belief (segments the trim),
    an active trend/note belief (drives the autumn-ramp lead), or an ACTIVE structural belief firing
    on a planned day. Everything else eligible is CONSIDERED, not INFORMED.
    """
    if b.status == "retired":
        return False
    if b.kind in ("note", "trend") and b.status == "active" and trend_active \
            and b.params.get("trend") == "up":
        return True
    if b.kind == "scale_pct" and "Picking" in b.activities and b.valid_from in boundaries:
        return any(b.active_on(d, decision_date) for d in scored_days)
    if b.status == "active" and b.kind not in ("note", "trend"):
        return any(b.active_on(d, decision_date) for d in scored_days)
    return False


def build_provenance(as_of: Optional[str] = None, halflife: float = 21.0, offset: float = 0.3,
                     trend_gain: float = 0.4, include_holdout: bool = True,
                     present=None, recs=None, volumes=None) -> ProvenanceGraph:
    """Walk the decisions forward and assemble the provenance graph.

    Each cycle is curated with as_of = its own decision Monday (honest, no peeking). Training cycles
    (with actuals) get a real Outcome; holdout cycles get a forecast Outcome (baseline-relative,
    no actual cost). `as_of` (optional) trims the graph to weeks decided strictly before that date.
    """
    present = present if present is not None else data.load_present()
    recs = recs or data.load_recommendations()
    volumes = volumes if volumes is not None else data.load_volumes()
    rec_op_by_date = {d: t for r in recs.values()
                      for d, t in r.operative_totals().items() if data.is_working_day(d)}

    pg = ProvenanceGraph()
    prev_week = None
    prev_trust: Dict[str, float] = {}

    for dd in sorted(recs):
        if as_of is not None and dd >= as_of:
            continue
        rec = recs[dd]
        planned = [d for d in rec.dates if data.is_working_day(d)]
        if not planned:
            continue
        scored = [d for d in planned if d in present]          # training days (have actuals)
        is_holdout = not scored
        if is_holdout and not include_holdout:
            continue
        week = _monday(dd)

        g = curate.build_graph()
        curate.curate(g, present, recs, as_of=week)
        engine = predict.Engine(g, halflife=halflife, offset=offset, trend_gain=trend_gain)
        ctx = Context(present, volumes, rec_op_by_date, week)
        plan = engine.plan_cycle(rec, planned, ctx)
        # representative k for the cycle (first planned day)
        k = engine.explain(rec, planned[0], ctx)["k"]
        dnode = pg.add_decision(week, sum(plan.values()), k, len(planned))

        boundaries = engine.boundaries
        trend_active = engine._trend_active
        for b in g.list():
            if as_of is not None and b.valid_from >= as_of:
                continue
            if b.valid_from > week:               # not yet captured at this decision
                continue
            pg.add_belief(b, _source_of(b))
            eligible = any(b.active_on(d, dd) for d in planned) or \
                (b.kind in ("note", "trend") and b.status != "retired")
            if not eligible:
                continue
            material = _materially_informs(b, planned, dd, boundaries, trend_active)
            pg.informed(b.id, week, material)
            # trust movement since the previous week this belief was seen -> UPDATED edge
            if b.id in prev_trust and abs(b.trust - prev_trust[b.id]) > 1e-9:
                pg.updated(week, b.id, b.trust - prev_trust[b.id])
            prev_trust[b.id] = b.trust

        # outcome
        if is_holdout:
            base_cost = score_plan({d: rec.operative_total(d) for d in planned},
                                   {d: rec.operative_total(d) for d in planned})  # =0; forecast
            pg.add_outcome(week, 0.0, 0.0, is_forecast=True)
        else:
            need = {d: present[d] for d in scored}
            base = {d: rec.operative_total(d) for d in scored}
            pg.add_outcome(week, score_plan(plan, need), score_plan(base, need), is_forecast=False)
        pg.resulted_in(week)

        # contradiction edges among captured beliefs (mirror the belief-graph edges)
        for e in g.edges:
            if e.kind == "contradicts" and f"belief:{e.src}" in pg.nodes \
                    and f"belief:{e.dst}" in pg.nodes:
                pg.contradicts(e.src, e.dst)

        if prev_week is not None:
            pg.preceded(prev_week, week)
        prev_week = week

    return pg


if __name__ == "__main__":
    pg = build_provenance()
    snap = pg.snapshot()
    print("PROVENANCE GRAPH (walk-forward, honest)")
    print("  node counts:", snap["counts"], " edges:", len(snap["edges"]))
    # trace the first training week with beliefs that informed it
    weeks = sorted(n["week"] for n in snap["nodes"] if n["type"] == "decision")
    for w in weeks:
        t = pg.trace(w)
        informed = [x for x in t["informed_by"] if x["role"] == "INFORMED"]
        if informed:
            print(f"\n  trace week {w}: plan {t['decision']['plan_total']} pd "
                  f"(k={t['decision']['k']}), outcome gap "
                  f"{t['outcome']['gap_closed_pct'] if t['outcome'] else '—'}%")
            for x in informed:
                print(f"    <- {x['belief']} (trust {x['trust']}, {x['scope']}) from {x['source']}")
            break
