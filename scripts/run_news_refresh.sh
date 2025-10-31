#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"

mkdir -p "$LOGDIR" "$REPO/data/news"
cd "$REPO"

# Make repo importable as a package and export .env to the shell
export PYTHONPATH="$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a

/usr/bin/flock -n /tmp/news_refresh.lock bash -lc "
  source '$REPO/.venv/bin/activate'
  cd '$REPO'
  '$REPO/.venv/bin/python' -m src.fetchers.news_refresh --date last60min --items 50 --cache false
" >> "$LOGDIR/news_refresh.log" 2>&1
