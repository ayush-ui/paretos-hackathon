#!/usr/bin/env bash
# Smoke-test every API endpoint against a running server.
# Usage: ./scripts/run_api.sh   (in one terminal), then ./scripts/test_api.sh   (in another)
set -euo pipefail
BASE="${1:-http://localhost:8000}"

# Pretty-print JSON if python3 is available, else raw.
pp() { python3 -m json.tool 2>/dev/null || cat; }
hr() { printf '\n=== %s ===\n' "$1"; }

hr "health";                 curl -s "$BASE/api/health" | pp
hr "summary";                curl -s "$BASE/api/summary" | pp
hr "cycles (first 2)";       curl -s "$BASE/api/cycles" | python3 -c "import sys,json;print(json.dumps(json.load(sys.stdin)[:2],indent=2))"
hr "holdout plan (first 3)"; curl -s "$BASE/api/plan/current" | python3 -c "import sys,json;print(json.dumps(json.load(sys.stdin)[:3],indent=2))"
hr "trace 2026-09-07 (training day)"; curl -s "$BASE/api/plan/2026-09-07/trace" | pp
hr "trace 2026-10-05 (holdout, leak-safe)"; curl -s "$BASE/api/plan/2026-10-05/trace" | pp
hr "graph end-state (counts)"; curl -s "$BASE/api/graph" | python3 -c "import sys,json;d=json.load(sys.stdin);print('nodes',len(d['nodes']),'edges',len(d['edges']))"
hr "graph as_of 2026-08-01"; curl -s "$BASE/api/graph?as_of=2026-08-01" | python3 -c "import sys,json;d=json.load(sys.stdin);print('nodes',len(d['nodes']),'(L11 hidden:', 'L11' not in [n['id'] for n in d['nodes']], ')')"
hr "belief L11";             curl -s "$BASE/api/beliefs/L11" | pp
hr "compounding (first row, slow ~15s first call)"; curl -s "$BASE/api/compounding" | python3 -c "import sys,json;print(json.dumps(json.load(sys.stdin)[0],indent=2))"
hr "validation (slow first call)"; curl -s "$BASE/api/validation" | python3 -c "import sys,json;d=json.load(sys.stdin);print('ablation top:',d['ablation'][0]);print('sensitivity:',d['sensitivity'])"

# --- LLM endpoints (work with or without ANTHROPIC_API_KEY) ---
hr "llm status";             curl -s "$BASE/api/llm/status" | pp
hr "explain 2026-09-07";     curl -s "$BASE/api/plan/2026-09-07/explain" | pp
hr "ask why";                curl -s -X POST "$BASE/api/ask" -H 'content-type: application/json' \
  -d '{"date":"2026-09-07","question":"Why did we trim the plan that day?"}' | pp

printf '\nAll endpoints hit.\n'
