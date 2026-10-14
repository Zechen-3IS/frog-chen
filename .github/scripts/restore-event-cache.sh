#!/usr/bin/env bash
# Restore event_scores / event_draws from the Pages branch so daily/live stay incremental.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PUBLISH_REPOSITORY="${PUBLISH_REPOSITORY:-${GITHUB_REPOSITORY:-Zechen-3IS/frog-chen}}"
PUBLISH_BRANCH="${PUBLISH_BRANCH:-pages}"
TOKEN="${PUBLISH_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"

mkdir -p "${ROOT}/data/event_scores" "${ROOT}/data/event_draws" "${ROOT}/data/event_day_rounds"

if [[ -z "${TOKEN}" ]]; then
  echo "no token; skip pages cache restore"
  exit 0
fi

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

clone_url="https://x-access-token:${TOKEN}@github.com/${PUBLISH_REPOSITORY}.git"
if ! git ls-remote --exit-code --heads "${clone_url}" "${PUBLISH_BRANCH}" >/dev/null 2>&1; then
  echo "pages branch missing; cold start"
  exit 0
fi

git clone --depth 1 --branch "${PUBLISH_BRANCH}" "${clone_url}" "${WORKDIR}/pages"
for dir in event_scores event_draws event_day_rounds; do
  src="${WORKDIR}/pages/data/${dir}"
  dst="${ROOT}/data/${dir}"
  if [[ -d "${src}" ]]; then
    mkdir -p "${dst}"
    cp -R "${src}/." "${dst}/"
    echo "restored data/${dir}: $(find "${dst}" -type f | wc -l | tr -d ' ') files"
  fi
done
