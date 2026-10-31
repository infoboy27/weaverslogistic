#!/usr/bin/env bash
# Cron (hourly): deploy new code from origin/main, but only commits whose CI tests passed.
# After the rebuild a smoke test runs against the public URL; if it fails the previous
# commit is rebuilt (rollback). Data is not in the checkout (WEAVERS_DATA_PATH), so a pull
# never touches it. Private repo: put a read-only GitHub token in secrets/github_token.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=infoboy27/weaverslogistic
COMPOSE="docker compose -f docker-compose.traefik.yml"
log() { echo "$(date '+%F %T') $*"; }

exec 9>/tmp/weaverslogistic-update.lock
flock -n 9 || { log "otra actualización en curso"; exit 0; }

git fetch -q origin main
current=$(git rev-parse HEAD)
target=$(git rev-parse origin/main)
[ "$current" = "$target" ] && exit 0

if ! git diff --name-only "$current" "$target" | grep -qv '^data/'; then
  git merge -q --ff-only "$target"   # data-only commits: nothing to rebuild
  exit 0
fi

auth=()
[ -s secrets/github_token ] && auth=(-H "Authorization: Bearer $(cat secrets/github_token)")
checks=$(curl -fsS "${auth[@]}" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO/commits/$target/check-runs?per_page=50") || { log "no pude leer el CI de $target"; exit 1; }
verdict=$(python3 - "$checks" <<'PY'
import json, sys
runs = {r["name"]: r for r in json.loads(sys.argv[1]).get("check_runs", [])}
needed = ["Pruebas", "Imagen Docker"]
if any(n not in runs or runs[n]["status"] != "completed" for n in needed):
    print("pending")
elif all(runs[n]["conclusion"] == "success" for n in needed):
    print("ok")
else:
    print("failed")
PY
)
case "$verdict" in
  pending) log "CI de ${target:0:7} todavía corre; reintento en la próxima hora"; exit 0 ;;
  failed)  log "CI de ${target:0:7} falló; NO se despliega"; exit 1 ;;
esac

log "desplegando ${current:0:7} -> ${target:0:7}"
git merge -q --ff-only "$target"
$COMPOSE build -q app && $COMPOSE up -d app

smoke() {
  local domain s
  domain=$(grep -E '^APP_DOMAIN=' .env | cut -d= -f2)
  for _ in $(seq 1 40); do
    s=$(docker inspect -f '{{.State.Health.Status}}' weaverslogistic-app 2>/dev/null || echo none)
    [ "$s" = healthy ] && break
    sleep 3
  done
  [ "$s" = healthy ] || return 1
  [ "$(curl -fsS -m 10 "https://$domain/_stcore/health")" = ok ] || return 1
  curl -fsSI -m 10 "https://$domain/" | grep -qi '^strict-transport-security' || return 1
}

if smoke; then
  log "OK ${target:0:7}"
else
  log "smoke test FALLÓ en ${target:0:7}; vuelvo a ${current:0:7}"
  git reset -q --hard "$current"
  $COMPOSE build -q app && $COMPOSE up -d app
  smoke && log "rollback OK" || log "rollback también falla: revisar a mano"
  exit 1
fi
