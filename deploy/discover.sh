#!/usr/bin/env bash
# Cron (daily): Google Trends discovery + ranking on the server, writing the live data
# folder (WEAVERS_DATA_PATH). Replaces the Windows task "Weavers FBA Discovery".
set -euo pipefail
cd "$(dirname "$0")/.."
DATA=$(grep -E '^WEAVERS_DATA_PATH=' .env | cut -d= -f2)
DATA=${DATA:-./data}
exec 9>/tmp/weaverslogistic-discover.lock
flock -n 9 || exit 0
{
  echo "===== $(date '+%F %T')"
  docker compose -f docker-compose.traefik.yml --profile jobs run --rm -T worker python -m scripts.discover
} >> "$DATA/discovery_log.txt" 2>&1
