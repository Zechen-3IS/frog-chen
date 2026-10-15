#!/usr/bin/env bash
# Trigger Update live (pick pages) via workflow_dispatch.
# Used by local LaunchAgent / external cron — GitHub's */15 schedule is unreliable.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="${PUBLISH_REPOSITORY:-Zechen-3IS/frog-chen}"
WORKFLOW="${LIVE_WORKFLOW:-update-live.yml}"
REF="${LIVE_REF:-main}"
LOG_DIR="${LIVE_DISPATCH_LOG_DIR:-$ROOT/logs}"
LOG_FILE="${LOG_DIR}/dispatch-live.log"

mkdir -p "${LOG_DIR}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

{
  echo "[$(ts)] dispatch ${REPO} workflow=${WORKFLOW} ref=${REF}"
  if ! command -v gh >/dev/null 2>&1; then
    echo "[$(ts)] ERROR: gh not found in PATH"
    exit 127
  fi
  gh workflow run "${WORKFLOW}" -R "${REPO}" --ref "${REF}"
  echo "[$(ts)] ok"
} >>"${LOG_FILE}" 2>&1
