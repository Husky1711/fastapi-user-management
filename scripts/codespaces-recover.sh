#!/usr/bin/env bash
# Recover from a failed Codespace postCreate — install deps and start all services.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=============================================="
echo " Codespaces recovery"
echo "=============================================="

bash .devcontainer/setup.sh
bash .devcontainer/start.sh

echo ""
echo "Recovery complete. Open the Web UI on port 5173 (Ports tab)."
