#!/usr/bin/env bash
# Cron (nightly): Postgres dump + live data + users/secrets, kept 14 days in BACKUP_DIR.
# Off-box copies are pulled from another machine (see PRODUCCION.md > Respaldos).
set -euo pipefail
cd "$(dirname "$0")/.."
BACKUP_DIR=${BACKUP_DIR:-/home/ubuntu/backups/weaverslogistic}
DATA=$(grep -E '^WEAVERS_DATA_PATH=' .env | cut -d= -f2)
DATA=${DATA:-./data}
stamp=$(date +%F)
umask 077
mkdir -p "$BACKUP_DIR"
docker compose -f docker-compose.traefik.yml exec -T db pg_dump -U weavers -Fc weavers > "$BACKUP_DIR/db-$stamp.dump"
tar czf "$BACKUP_DIR/files-$stamp.tgz" --exclude='*.lock' -C "$(dirname "$(realpath "$DATA")")" "$(basename "$(realpath "$DATA")")" \
  -C "$PWD" secrets .env
# A backup that can't be read is not a backup.
tar tzf "$BACKUP_DIR/files-$stamp.tgz" > /dev/null
[ -s "$BACKUP_DIR/db-$stamp.dump" ]
find "$BACKUP_DIR" -maxdepth 1 -name '*-20*' -mtime +14 -delete
echo "$(date '+%F %T') backup OK $(du -sh "$BACKUP_DIR" | cut -f1)"
