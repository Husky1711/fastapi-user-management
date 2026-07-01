#!/usr/bin/env bash
# Shared helpers for Codespaces setup and start scripts.

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
  docker exec -i fastapi-mysql mysql -ufastapi -pfastapi fastapi_users < scripts/seed.sql
}

frontend_is_running() {
  pgrep -f "vite.*--port ${FRONTEND_PORT:-5173}" >/dev/null 2>&1 \
    || pgrep -f "vite.*${FRONTEND_PORT:-5173}" >/dev/null 2>&1
}

start_frontend() {
  local port="${FRONTEND_PORT:-5173}"

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
    echo "npm not found — install Node.js or rebuild the Codespace with the node feature."
    return 1
  fi

  mkdir -p logs
  pushd frontend >/dev/null
  if [[ ! -d node_modules ]]; then
    echo "Installing frontend dependencies..."
    npm ci
  fi

  nohup npm run dev -- --host 0.0.0.0 --port "${port}" >> ../logs/vite.log 2>&1 &
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
  # Vite proxies /api to the API — same-origin in the browser; no extra CORS needed for UI.
  if [[ -n "${CODESPACE_NAME:-}" ]]; then
    local ui_origin="https://${CODESPACE_NAME}-5173.app.github.dev"
    export SECURITY__CORS_ORIGINS="[\"http://localhost:5173\",\"http://127.0.0.1:5173\",\"${ui_origin}\"]"
  fi
}

fastapi_is_running() {
  pgrep -f "uvicorn main:app.*--port 9000" >/dev/null 2>&1
}

start_fastapi() {
  if fastapi_is_running; then
    echo "FastAPI is already running on port 9000."
    return 0
  fi

  mkdir -p logs
  # shellcheck disable=SC1091
  source .venv/bin/activate
  nohup uvicorn main:app --host 0.0.0.0 --port 9000 --reload >> logs/uvicorn.log 2>&1 &
  disown

  for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:9000/health >/dev/null 2>&1; then
      echo "FastAPI is running on http://0.0.0.0:9000 (docs: /docs)"
      return 0
    fi
    sleep 1
  done

  echo "FastAPI process started but health check did not pass yet."
  echo "Check logs/uvicorn.log for details."
  return 0
}
