#!/usr/bin/env bash
# Quick health check for Codespaces — API, UI, Docker, logs.
set -uo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=.devcontainer/lib.sh
source .devcontainer/lib.sh

API_PORT="$(read_app_port)"
UI_PORT="${FRONTEND_PORT:-5173}"

echo "=============================================="
echo " Codespaces diagnose"
echo "=============================================="
echo "CODESPACE_NAME: ${CODESPACE_NAME:-<not set>}"
echo "API port:       ${API_PORT}"
echo "UI port:        ${UI_PORT}"
echo ""

echo "--- Docker ---"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "Docker not available"
echo ""

echo "--- Processes ---"
pgrep -af "uvicorn main:app" || echo "No uvicorn process"
pgrep -af "vite" || echo "No vite process"
echo ""

echo "--- HTTP checks (local) ---"
for path in "/health" "/docs" "/openapi.json"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${API_PORT}${path}" || echo "000")
  echo "API ${path}: HTTP ${code}"
done
ui_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${UI_PORT}/" || echo "000")
echo "UI /: HTTP ${ui_code}"
login_code=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "http://127.0.0.1:${UI_PORT}/api/v1/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testadmin","password":"admin123"}' || echo "000")
echo "UI proxy POST /api/v1/login: HTTP ${login_code}"
echo ""

if [[ -n "${CODESPACE_NAME:-}" ]]; then
  echo "--- Public URLs ---"
  echo "UI:  https://${CODESPACE_NAME}-${UI_PORT}.app.github.dev"
  echo "API: https://${CODESPACE_NAME}-${API_PORT}.app.github.dev/docs"
  echo ""
fi

echo "--- Last log lines ---"
for log in logs/uvicorn.log logs/vite.log; do
  if [[ -f "${log}" ]]; then
    echo ">> ${log}"
    tail -n 15 "${log}"
    echo ""
  fi
done

echo "Fix: bash scripts/codespaces-recover.sh"
