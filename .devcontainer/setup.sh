#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${GIT_REPOSITORY_URL:-https://github.com/Husky1711/fastapi-user-management.git}"
BRANCH="${GIT_BRANCH:-feature/codespaces-local-db}"

echo "=============================================="
echo " FastAPI User Management — Codespaces setup"
echo " Repository: ${REPO_URL}"
echo " Branch:     ${BRANCH}"
echo "=============================================="

cd "$(dirname "$0")/.."

# Ensure we are on the intended feature branch
git fetch origin "${BRANCH}" 2>/dev/null || true
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  git checkout "${BRANCH}"
elif git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  git checkout -B "${BRANCH}" "origin/${BRANCH}"
fi

# Python virtual environment
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Codespaces-specific environment (local MySQL + Redis)
cp -n .env.codespaces.example .env 2>/dev/null || cp .env.codespaces.example .env

# Start local database stack
docker compose -f docker-compose.codespaces.yml up -d

echo "Waiting for MySQL..."
for i in $(seq 1 60); do
  if docker exec fastapi-mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null; then
    echo "MySQL is ready."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "MySQL did not become ready in time."
    exit 1
  fi
  sleep 2
done

# Create tables from SQLAlchemy models
python scripts/bootstrap_local_db.py

# Sample data
docker exec -i fastapi-mysql mysql -ufastapi -pfastapi fastapi_users < scripts/seed.sql

echo ""
echo "Setup complete."
echo "  Repo:   ${REPO_URL}"
echo "  Branch: ${BRANCH}"
echo "  API:    http://localhost:9000/docs"
echo ""
echo "Start the app:"
echo "  source .venv/bin/activate"
echo "  uvicorn main:app --host 0.0.0.0 --port 9000 --reload"
