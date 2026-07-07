#!/usr/bin/env bash
# Shared helpers for Codespaces setup and start scripts.

# Load canonical ports (codespaces.ports.env)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${REPO_ROOT}/codespaces.ports.env" ]]; then
  # shellcheck source=../codespaces.ports.env
  source "${REPO_ROOT}/codespaces.ports.env"
fi
export CODESPACES_API_PORT="${CODESPACES_API_PORT:-9000}"
export CODESPACES_UI_PORT="${CODESPACES_UI_PORT:-5173}"
export FRONTEND_PORT="${CODESPACES_UI_PORT}"

wait_for_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker CLI not found."
    return 1
  fi

  echo "Waiting for Docker daemon..."
  for i in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      echo "Docker is ready."
      return 0
    fi
    sleep 2
  done

  echo "Docker daemon did not become ready in time."
  return 1
}

wait_for_mysql() {
  echo "Waiting for MySQL..."
  for i in $(seq 1 60); do
    if docker exec fastapi-mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null; then
      echo "MySQL is ready."
      return 0
    fi
    sleep 2
  done
  echo "MySQL did not become ready in time."
  return 1
}

wait_for_redis() {
  for i in $(seq 1 30); do
    if docker exec fastapi-redis redis-cli ping 2>/dev/null | grep -q PONG; then
      echo "Redis is ready."
      return 0
    fi
    sleep 1
  done
  echo "Redis did not become ready in time."
  return 1
}

bootstrap_database() {
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python scripts/bootstrap_local_db.py
}

seed_database() {
  if [[ ! -f scripts/seed.sql ]]; then
    echo "scripts/seed.sql not found — skipping seed."
    return 0
  fi
  docker exec -i fastapi-mysql mysql -ufastapi -pfastapi fastapi_users < scripts/seed.sql \
    || echo "WARN: seed.sql had errors (may be safe if data already exists)."
}

frontend_is_running() {
  pgrep -f "vite.*--port ${CODESPACES_UI_PORT}" >/dev/null 2>&1 \
    || pgrep -f "vite.*${CODESPACES_UI_PORT}" >/dev/null 2>&1
}

start_frontend() {
  local port="${CODESPACES_UI_PORT}"

  if [[ ! -d frontend ]]; then
    echo "frontend/ not found — skipping UI."
    return 0
  fi

  if frontend_is_running; then
    echo "Web UI is already running on port ${port}."
    print_frontend_urls "${port}"
    return 0
  fi

  if ! command -v npm >/dev/null 2>&1; then
    export PATH="/usr/local/share/nvm/current/bin:${PATH}"
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "WARN: npm not found — Web UI not started. Run: bash scripts/codespaces-ui-start.sh"
    return 0
  fi

  mkdir -p logs
  if [[ -f frontend/.env.codespaces ]]; then
    cp -f frontend/.env.codespaces frontend/.env
  fi
  pushd frontend >/dev/null
  if [[ ! -d node_modules ]]; then
    echo "Installing frontend dependencies..."
    npm ci
  fi

  nohup env VITE_API_PROXY_TARGET="http://127.0.0.1:${CODESPACES_API_PORT}" \
    npm run dev -- --host 0.0.0.0 --port "${port}" --strictPort >> ../logs/vite.log 2>&1 &
  disown
  popd >/dev/null

  for i in $(seq 1 45); do
    if curl -sf "http://127.0.0.1:${port}/" >/dev/null 2>&1; then
      echo "Web UI is running on http://0.0.0.0:${port}"
      print_frontend_urls "${port}"
      return 0
    fi
    sleep 1
  done

  echo "Frontend process started but health check did not pass yet."
  echo "Check logs/vite.log for details."
  return 0
}

print_frontend_urls() {
  local port="${1:-5173}"
  if [[ -n "${CODESPACE_NAME:-}" ]]; then
    echo "  Codespaces UI: https://${CODESPACE_NAME}-${port}.app.github.dev"
  fi
  echo "  Local UI:      http://localhost:${port}"
  echo "  UI logs:       tail -f logs/vite.log"
}

configure_codespace_env() {
  if [[ -n "${CODESPACE_NAME:-}" ]]; then
    export CODESPACE_NAME
    local ui_origin="https://${CODESPACE_NAME}-${CODESPACES_UI_PORT}.app.github.dev"
    local api_origin="https://${CODESPACE_NAME}-${CODESPACES_API_PORT}.app.github.dev"
    export SECURITY__CORS_ORIGINS="[\"http://localhost:${CODESPACES_UI_PORT}\",\"http://127.0.0.1:${CODESPACES_UI_PORT}\",\"${ui_origin}\",\"${api_origin}\"]"
  fi
}

read_app_port() {
  echo "${CODESPACES_API_PORT}"
}

stop_stale_api_processes() {
  local port
  port="$(read_app_port)"
  # Kill uvicorn on wrong ports (e.g. 8000 from manual runs or old config)
  while read -r stale_port; do
    if [[ "${stale_port}" != "${port}" ]]; then
      echo "Stopping stale API on port ${stale_port}..."
      pkill -f "uvicorn main:app.*--port ${stale_port}" 2>/dev/null || true
    fi
  done < <(pgrep -af "uvicorn main:app" 2>/dev/null | grep -oE '\-\-port [0-9]+' | awk '{print $2}' | sort -u)
}

fastapi_is_running() {
  local port
  port="$(read_app_port)"
  pgrep -f "uvicorn main:app.*--port ${port}" >/dev/null 2>&1
}

start_fastapi() {
  local port
  port="$(read_app_port)"

  stop_stale_api_processes

  if fastapi_is_running; then
    echo "FastAPI is already running on port ${port}."
    return 0
  fi

  mkdir -p logs
  # shellcheck disable=SC1091
  source .venv/bin/activate
  configure_codespace_env
  nohup uvicorn main:app --host 0.0.0.0 --port "${port}" --reload >> logs/uvicorn.log 2>&1 &
  disown

  for i in $(seq 1 45); do
    if curl -sf "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      echo "FastAPI is running on http://0.0.0.0:${port} (docs: /docs)"
      if [[ -n "${CODESPACE_NAME:-}" ]]; then
        echo "  Public API: https://${CODESPACE_NAME}-${port}.app.github.dev/docs"
      fi
      return 0
    fi
    sleep 1
  done

  echo "FastAPI process started but health check did not pass yet."
  echo "Check logs/uvicorn.log for details."
  return 0
}
