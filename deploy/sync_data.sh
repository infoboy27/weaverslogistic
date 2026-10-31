#!/usr/bin/env bash
# Cron (server): pull the daily scan data committed by the Windows discovery task.
# Edits made in the dashboard (pipeline, competencia...) are kept through --autostash.
set -euo pipefail
cd "$(dirname "$0")/.."
before=$(git rev-parse HEAD)
git pull --ff-only --autostash -q origin main
after=$(git rev-parse HEAD)
# Code changed (not only data): rebuild the app.
if [ "$before" != "$after" ] && git diff --name-only "$before" "$after" | grep -qv '^data/'; then
  docker compose -f docker-compose.traefik.yml up -d --build app
fi
