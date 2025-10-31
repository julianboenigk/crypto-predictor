#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"

mkdir -p "$LOGDIR" "$REPO/data/sentiment"
cd "$REPO"

# Make repo importable as a package and export .env to the shell
export PYTHONPATH="$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a

/usr/bin/flock -n /tmp/sentiment_refresh.lock bash -lc "
  source '$REPO/.venv/bin/activate'
  cd '$REPO'
  '$REPO/.venv/bin/python' -m src.fetchers.sentiment_refresh --date yesterday --cache false
" >> "$LOGDIR/sentiment_refresh.log" 2>&1
