"""Generate / refresh the LLM-first belief-extraction cache (state/belief_extractions.json).

Reads each decision-log note's prose with Claude (one at a time, in date order, with prior beliefs
as context), writes the structured claims + contradicts/supersedes to the cache. Requires
ANTHROPIC_API_KEY. The result is meant to be HUMAN-REVIEWED and committed — it then becomes the
deterministic input to the scored backtest (build_graph(use_llm=True)).

Run:  python3 scripts/extract_beliefs.py            # fill cache misses
      python3 scripts/extract_beliefs.py --refresh   # re-extract every note (rewrites the past!)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import extract, llm  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-extract every note (else only misses)")
    args = ap.parse_args()
    if not llm.available():
        print("ANTHROPIC_API_KEY not set / anthropic missing — cannot extract. (Fallback path needs no cache.)")
        sys.exit(1)
    beliefs, edges = extract.extracted_beliefs(use_llm=True, refresh=args.refresh)
    cache = extract.load_cache()
    print(f"extracted {len(cache)} notes -> {extract.CACHE_PATH}")
    for cid in sorted(cache):
        rec = cache[cid]
        rel = ""
        if rec.get("supersedes"):
            rel += f"  supersedes={rec['supersedes']}"
        if rec.get("contradicts"):
            rel += f"  contradicts={rec['contradicts']}"
        print(f"  {cid}: {json.dumps(rec['claim'])}{rel}")


if __name__ == "__main__":
    main()
