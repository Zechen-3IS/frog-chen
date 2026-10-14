#!/usr/bin/env bash
# Publish generated HTML to a Pages repo/branch.
# Defaults for local/dev: Zechen-3IS/frog-chen@pages
# In Actions, workflows override via PUBLISH_* env (same repo + GITHUB_TOKEN for testing).
set -euo pipefail

mode="${1:?usage: push-pages.sh <live|daily> [commit message]}"
message="${2:-自动更新幸存者页面 (${mode})}"

if [[ "${mode}" != "live" && "${mode}" != "daily" ]]; then
  echo "mode must be live or daily" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PUBLISH_REPOSITORY="${PUBLISH_REPOSITORY:-Zechen-3IS/frog-chen}"
PUBLISH_BRANCH="${PUBLISH_BRANCH:-pages}"
TOKEN="${PUBLISH_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"

if [[ -z "${TOKEN}" ]]; then
  echo "PUBLISH_TOKEN (or GH_TOKEN / GITHUB_TOKEN) is required" >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
cleanup() { rm -rf "${WORKDIR}"; }
trap cleanup EXIT

clone_url="https://x-access-token:${TOKEN}@github.com/${PUBLISH_REPOSITORY}.git"

if git ls-remote --exit-code --heads "${clone_url}" "${PUBLISH_BRANCH}" >/dev/null 2>&1; then
  git clone --depth 1 --branch "${PUBLISH_BRANCH}" "${clone_url}" "${WORKDIR}/pages"
else
  git clone --depth 1 "${clone_url}" "${WORKDIR}/pages"
  cd "${WORKDIR}/pages"
  git checkout --orphan "${PUBLISH_BRANCH}"
  git rm -rf . >/dev/null 2>&1 || true
fi

copy_if_exists() {
  local rel="$1"
  local src="${ROOT}/${rel}"
  local dst="${WORKDIR}/pages/${rel}"
  if [[ -e "${src}" ]]; then
    mkdir -p "$(dirname "${dst}")"
    if [[ -d "${src}" ]]; then
      rm -rf "${dst}"
      cp -R "${src}" "${dst}"
    else
      cp "${src}" "${dst}"
    fi
  fi
}

# Pick-related surfaces (15-minute job)
LIVE_PATHS=(
  index.html
  atp_ranking.html
  wta_ranking.html
  atp_race_ranking.html
  wta_race_ranking.html
  combined_instant_ranking.html
  combined_ranking.html
  survivor_calendar.html
  survivor_calendar_atp.html
  survivor_calendar_wta.html
  players.json
  data/players.json
  data/weather_cards_cache.json
  data/breakdown_live_atp.js
  data/breakdown_live_atp.json
  data/breakdown_live_wta.js
  data/breakdown_live_wta.json
  data/breakdown_race_atp.js
  data/breakdown_race_atp.json
  data/breakdown_race_wta.js
  data/breakdown_race_wta.json
  data/event_scores
  data/event_draws
  data/event_day_rounds
  assets
)

cd "${ROOT}"
YEAR="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
print(cfg.get("year") or "")
PY
)"

for rel in "${LIVE_PATHS[@]}"; do
  copy_if_exists "${rel}"
done
if [[ -n "${YEAR}" ]]; then
  copy_if_exists "events/${YEAR}"
fi

if [[ "${mode}" == "daily" ]]; then
  DAILY_PATHS=(
    atp_show.html
    wta_show.html
    atp_champion.html
    wta_champion.html
    atpkiller.html
    wtakiller.html
    2026atpkiller.html
    2026wtakiller.html
    h2h_atp.html
    h2h_wta.html
    data/player_events.json
    data/h2h_records.csv
    data/champions.csv
    events
  )
  for rel in "${DAILY_PATHS[@]}"; do
    copy_if_exists "${rel}"
  done
fi

cd "${WORKDIR}/pages"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

git add -A
if git diff --cached --quiet; then
  echo "unchanged"
  exit 0
fi

git commit -m "${message}"

for attempt in 1 2 3 4 5; do
  if git push -u origin "HEAD:${PUBLISH_BRANCH}"; then
    echo "pushed to ${PUBLISH_REPOSITORY}@${PUBLISH_BRANCH}"
    exit 0
  fi
  echo "push rejected, retry ${attempt}"
  git pull --rebase origin "${PUBLISH_BRANCH}" || true
  sleep $((attempt * 8))
done

echo "push failed after retries" >&2
exit 1
