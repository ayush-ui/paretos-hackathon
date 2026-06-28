#!/usr/bin/env bash
# Run the Discord absence bot. Needs DISCORD_BOT_TOKEN in .env and the Helios API on :8000.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
  echo "⚠️  Helios API not reachable on :8000 — start it first (scripts/run_api.sh or uvicorn)." >&2
fi

exec python3 -m bot.main
