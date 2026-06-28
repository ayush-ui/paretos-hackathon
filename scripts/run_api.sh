#!/usr/bin/env bash
# Start the FastAPI backend. Reads ANTHROPIC_API_KEY from .env automatically (via python-dotenv).
# Docs/Swagger UI: http://localhost:8000/docs
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${1:-8000}"
echo "Starting API on http://localhost:${PORT}  (Ctrl-C to stop)"
echo "Interactive docs at http://localhost:${PORT}/docs"
exec python3 -m uvicorn api.main:app --reload --port "${PORT}"
