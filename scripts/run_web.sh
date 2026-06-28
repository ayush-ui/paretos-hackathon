#!/usr/bin/env bash
# Run the full stack for local dev: FastAPI (:8000) + Vite (:5173, proxies /api).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Starting API on :8000 …"
(cd "$ROOT" && uvicorn api.main:app --port 8000 >/tmp/helios-api.log 2>&1 &)

# wait for API health
for _ in $(seq 1 30); do
  curl -sf http://localhost:8000/api/health >/dev/null 2>&1 && break
  sleep 1
done
echo "API up. Starting web on :5173 …"
cd "$ROOT/web"
[ -d node_modules ] || npm install
exec npm run dev
