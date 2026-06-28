#!/usr/bin/env bash
# Run the engine offline (no server): backtest ladder, compounding loop, validation, submission,
# belief graph, and the unit-test suite. Useful to sanity-check everything in one shot.
set -euo pipefail
cd "$(dirname "$0")/.."

hr() { printf '\n========== %s ==========\n' "$1"; }

hr "TEST SUITE";          python3 -m pytest tests/ -q
hr "BACKTEST LADDER";     python3 eval/backtest.py
hr "VALIDATION";          python3 eval/validate.py
hr "COMPOUNDING LOOP";    python3 eval/compounding.py
hr "BELIEF GRAPH";        python3 eval/show_graph.py
hr "SUBMISSION";          python3 eval/submit.py
