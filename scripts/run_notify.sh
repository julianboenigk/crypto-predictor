#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"

mkdir -p "$LOGDIR" "$REPO/data/state"
cd "$REPO"

/usr/bin/flock -n /tmp/notify_from_log.lock bash -lc "
  source '$REPO/.venv/bin/activate'
  cd '$REPO'
  set -a
  [ -f .env ] && . ./.env || true
  set +a
  python -m src.utils.notify_from_log --log data/logs/main.log
" >> "$LOGDIR/notify_from_log.log" 2>&1
