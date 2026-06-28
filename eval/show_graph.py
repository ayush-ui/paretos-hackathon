"""Render the curated belief graph as text — the knowledge layer made visible (Phase 5/6 prep).

Run: python3 eval/show_graph.py            # end-state (all training data)
     python3 eval/show_graph.py 2026-07-01 # as the graph looked on that date (before L08 retired)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import data, curate  # noqa: E402

if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else None
    g = curate.build_graph()
    curate.curate(g, data.load_present(), data.load_recommendations(), as_of=as_of)
    header = "as of %s (walk-forward view)" % as_of if as_of else "end-state (all training data)"
    print("Curated belief graph — %s\n" % header)
    print(g.render_text(as_of=as_of))
    # also persist the JSON the frontend / a Neo4j export would consume
    out = os.path.join(data.PROJECT_ROOT, "submissions", "belief_graph.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    g.save(out)
    print("\nJSON graph -> %s" % out)
