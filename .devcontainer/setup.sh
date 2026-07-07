#!/usr/bin/env bash
# One-time Codespace setup: venv, Python deps, frontend deps.
# Does NOT start Docker/API/UI — postStartCommand runs start.sh for that.
set -euo pipefail

REPO_URL="${GIT_REPOSITORY_URL:-https://github.com/Husky1711/fastapi-user-management.git}"
BRANCH="${GIT_BRANCH:-feature/codespaces-local-db}"

echo "=============================================="
echo " FastAPI User Management — Codespaces setup"
echo " Repository: ${REPO_URL}"
echo " Branch:     ${BRANCH}"
echo "=============================================="

cd "$(dirname "$0")/.."

# Best-effort branch sync (Codespace may already be on the right ref)
if git rev-parse --git-dir >/dev/null 2>&1; then
  git fetch origin "${BRANCH}" 2>/dev/null || true
  if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    git checkout "${BRANCH}" 2>/dev/null || true
  elif git show-ref --verify --quiet "refs/remotes/origin/${BRANCH}"; then
    git checkout -B "${BRANCH}" "origin/${BRANCH}" 2>/dev/null || true
  fi
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp -n .env.codespaces.example .env 2>/dev/null || cp .env.codespaces.example .env

if [[ -f codespaces.ports.env ]]; then
  # shellcheck source=codespaces.ports.env
  source codespaces.ports.env
  if grep -q '^APP__PORT=' .env; then
    sed -i "s/^APP__PORT=.*/APP__PORT=${CODESPACES_API_PORT}/" .env
  else
    echo "APP__PORT=${CODESPACES_API_PORT}" >> .env
  fi
fi

install_frontend_deps() {
  if [[ ! -d frontend ]]; then
    echo "frontend/ not found — skipping npm install."
    return 0
  fi

  # Node feature may not be on PATH immediately in some builds — try common locations.
  if ! command -v npm >/dev/null 2>&1; then
    export PATH="/usr/local/share/nvm/current/bin:${PATH}"
  fi
  if ! command -v npm >/dev/null 2>&1; then
    echo "WARN: npm not found — frontend deps skipped. Rebuild Codespace or run: cd frontend && npm ci"
    return 0
  fi

  echo "Installing frontend dependencies..."
  if [[ -f frontend/.env.codespaces ]]; then
    cp -f frontend/.env.codespaces frontend/.env
  fi
  (cd frontend && (npm ci || npm install))
}

install_frontend_deps

echo ""
echo "First-time setup complete (dependencies only)."
echo "Services start via postStartCommand or manually:"
echo "  bash .devcontainer/start.sh"
