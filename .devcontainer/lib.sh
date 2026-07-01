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
