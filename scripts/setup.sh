#!/usr/bin/env bash
# One-time setup: install Python deps. Run from the project root.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Installing Python dependencies..."
python3 -m pip install -r requirements.txt

echo
echo "Done. Make sure .env contains ANTHROPIC_API_KEY (copy .env.example if needed)."
echo "Next: ./scripts/run_api.sh   (start the backend)"
