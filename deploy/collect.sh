#!/usr/bin/env bash
# Cron (daily): SP-API catalog snapshot (BSR, brand, price, sellers) for the researched keywords,
# into the live data folder (WEAVERS_DATA_PATH/catalog). Feeds the Marcas page.
set -euo pipefail
cd "$(dirname "$0")/.."
DATA=$(grep -E '^WEAVERS_DATA_PATH=' .env | cut -d= -f2)
DATA=${DATA:-./data}
exec 9>/tmp/weaverslogistic-collect.lock
flock -n 9 || exit 0
{
  echo "===== $(date '+%F %T')"
  docker compose -f docker-compose.traefik.yml --profile jobs run --rm -T worker python -m scripts.collect_catalog
} >> "$DATA/catalog_log.txt" 2>&1
