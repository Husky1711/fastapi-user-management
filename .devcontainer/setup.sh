#!/usr/bin/env bash
# One-time Codespace setup: branch, venv, dependencies, then start all services.
set -euo pipefail

REPO_URL="${GIT_REPOSITORY_URL:-https://github.com/Husky1711/fastapi-user-management.git}"
BRANCH="${GIT_BRANCH:-feature/codespaces-local-db}"

echo "=============================================="
echo " FastAPI User Management — Codespaces setup"
echo " Repository: ${REPO_URL}"
echo " Branch:     ${BRANCH}"
echo "=============================================="

cd "$(dirname "$0")/.."

git fetch origin "${BRANCH}" 2>/dev/null || true
if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  git checkout "${BRANCH}"
elif git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
  git checkout -B "${BRANCH}" "origin/${BRANCH}"
fi

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp -n .env.codespaces.example .env 2>/dev/null || cp .env.codespaces.example .env

echo ""
echo "First-time setup complete. Starting services..."
bash .devcontainer/start.sh
