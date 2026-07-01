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

docker compose -f docker-compose.codespaces.yml up -d
wait_for_mysql
wait_for_redis

bootstrap_database
seed_database
start_fastapi

echo ""
echo "Codespace is ready."
echo "  API docs: http://localhost:9000/docs"
echo "  Logs:     tail -f logs/uvicorn.log"
echo "  Restart:  bash .devcontainer/start.sh"
