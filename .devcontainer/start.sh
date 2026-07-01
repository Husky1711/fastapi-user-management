#!/usr/bin/env bash
# Runs on every Codespace start (and at the end of first-time setup).
# Starts MySQL + Redis, prepares schema/seed data, and launches FastAPI in the background.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=.devcontainer/lib.sh
source .devcontainer/lib.sh

echo "=============================================="
echo " Starting FastAPI User Management services"
echo "=============================================="

if [[ ! -d .venv ]]; then
  echo ".venv not found — run setup first or rebuild the Codespace."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.codespaces.example .env
fi

if ! wait_for_docker; then
  echo "ERROR: Docker is not available. Open a new terminal and run: bash .devcontainer/start.sh"
  exit 1
fi

docker compose -f docker-compose.codespaces.yml up -d
wait_for_mysql
wait_for_redis

bootstrap_database
seed_database
configure_codespace_env
start_fastapi
start_frontend

echo ""
echo "Codespace is ready."
echo "  Web UI:   http://localhost:5173"
if [[ -n "${CODESPACE_NAME:-}" ]]; then
  echo "  Public:   https://${CODESPACE_NAME}-5173.app.github.dev"
fi
echo "  API docs: http://localhost:9000/docs"
echo "  API logs: tail -f logs/uvicorn.log"
echo "  UI logs:  tail -f logs/vite.log"
echo "  Restart:  bash .devcontainer/start.sh"
echo "  UI only:  bash scripts/codespaces-ui-start.sh"
