#!/usr/bin/env bash
# Trigger Update live (pick pages) via workflow_dispatch.
# Used by local LaunchAgent — GitHub's */15 schedule is unreliable.
#
#   dispatch-live.sh            # scheduled tick (:00/:15/:30/:45)
#   dispatch-live.sh --catchup  # only if the last tick failed
#
# A failed tick retries 20s / 40s / 80s. If those still fail, a pending flag
# is left for the 5-minute catch-up agent.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="${PUBLISH_REPOSITORY:-Zechen-3IS/frog-chen}"
WORKFLOW="${LIVE_WORKFLOW:-update-live.yml}"
REF="${LIVE_REF:-main}"
LOG_DIR="${LIVE_DISPATCH_LOG_DIR:-$ROOT/logs}"
LOG_FILE="${LOG_DIR}/dispatch-live.log"
PENDING_FILE="${LOG_DIR}/dispatch-live.pending"
LOCK_DIR="${LOG_DIR}/dispatch-live.lock"

MODE="tick"
if [[ "${1:-}" == "--catchup" ]]; then
  MODE="catchup"
fi

mkdir -p "${LOG_DIR}"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [[ "${MODE}" == "catchup" && ! -f "${PENDING_FILE}" ]]; then
  exit 0
fi

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  {
    echo "[$(ts)] ${MODE} skip: another dispatch is running"
  } >>"${LOG_FILE}"
  exit 0
fi
cleanup() { rmdir "${LOCK_DIR}" 2>/dev/null || true; }
trap cleanup EXIT

# 20s, 40s, 80s after the first try (~2 min).
RETRY_WAITS=(20 40 80)

dispatch_once() {
  gh workflow run "${WORKFLOW}" -R "${REPO}" --ref "${REF}"
}

{
  echo "[$(ts)] ${MODE} dispatch ${REPO} workflow=${WORKFLOW} ref=${REF}"
  if ! command -v gh >/dev/null 2>&1; then
    echo "[$(ts)] ERROR: gh not found in PATH"
    date '+%Y-%m-%d %H:%M:%S' >"${PENDING_FILE}"
    exit 127
  fi

  attempt=1
  max=$((${#RETRY_WAITS[@]} + 1))
  while true; do
    if dispatch_once; then
      rm -f "${PENDING_FILE}"
      echo "[$(ts)] ok (attempt ${attempt}/${max})"
      exit 0
    fi
    if (( attempt > ${#RETRY_WAITS[@]} )); then
      date '+%Y-%m-%d %H:%M:%S' >"${PENDING_FILE}"
      echo "[$(ts)] failed after ${attempt} attempts; pending catch-up"
      exit 1
    fi
    wait_s="${RETRY_WAITS[$((attempt - 1))]}"
    echo "[$(ts)] attempt ${attempt} failed; retry in ${wait_s}s"
    sleep "${wait_s}"
    attempt=$((attempt + 1))
  done
} >>"${LOG_FILE}" 2>&1
