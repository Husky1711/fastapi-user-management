#!/usr/bin/env bash
# Manual entry point — same as automatic Codespace start.
set -euo pipefail
exec bash "$(dirname "$0")/../.devcontainer/start.sh"
