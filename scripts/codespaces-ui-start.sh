#!/usr/bin/env bash
# Start or restart the Web UI (Vite) in Codespaces / local dev.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=.devcontainer/lib.sh
source .devcontainer/lib.sh

PORT="${FRONTEND_PORT:-5173}"

echo "=============================================="
echo " Starting Web UI on port ${PORT}"
echo "=============================================="

if frontend_is_running; then
  echo "Stopping existing Vite process..."
  pkill -f "vite.*--port ${PORT}" 2>/dev/null || pkill -f "vite.*${PORT}" 2>/dev/null || true
  sleep 1
fi

configure_codespace_env
start_frontend
