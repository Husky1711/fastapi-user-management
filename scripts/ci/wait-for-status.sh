#!/usr/bin/env sh
# Poll a URL until it returns the expected HTTP status, or fail after a number of seconds.
# Usage: scripts/ci/wait-for-status.sh <url> <expected-status> [timeout-seconds]
set -eu

url="$1"
expected="$2"
timeout="${3:-30}"

code="000"
i=0
while [ "$i" -lt "$timeout" ]; do
  code=$(curl -s -o /dev/null -w '%{http_code}' "$url" || true)
  if [ "$code" = "$expected" ]; then
    echo "$url -> $code (after ${i}s)"
    exit 0
  fi
  i=$((i + 1))
  sleep 1
done
echo "$url -> $code, expected $expected within ${timeout}s" >&2
exit 1
