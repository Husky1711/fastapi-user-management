#!/usr/bin/env bash
# ADR-002 post-deploy smoke for staging/production (see docs/ADR-002-deployment-topology.md).
#
# Required:
#   STAGING_API_URL   e.g. https://api.staging.example.com
#
# Optional:
#   STAGING_APP_URL   e.g. https://app.staging.example.com  (UI alive check)
#   STAGING_ORIGIN    defaults to STAGING_APP_URL or CHECKLIST_ORIGIN
#   CHECKLIST_USER    defaults to testadmin
#   CHECKLIST_PASSWORD defaults to admin123
#
# Example:
#   STAGING_API_URL=https://api.staging.example.com \
#   STAGING_APP_URL=https://app.staging.example.com \
#   bash scripts/staging_post_deploy_smoke.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_URL="${STAGING_API_URL:?Set STAGING_API_URL (e.g. https://api.staging.example.com)}"
export CHECKLIST_BASE_URL="${API_URL%/}"
export CHECKLIST_APP_URL="${STAGING_APP_URL:-}"
export CHECKLIST_ORIGIN="${STAGING_ORIGIN:-${STAGING_APP_URL:-http://localhost:5173}}"

echo "== ADR-002 post-deploy smoke =="
echo "API:    $CHECKLIST_BASE_URL"
echo "App:    ${CHECKLIST_APP_URL:-<skipped>}"
echo "Origin: $CHECKLIST_ORIGIN"

python scripts/curl_auth_checklist.py
echo "== post-deploy smoke passed =="
