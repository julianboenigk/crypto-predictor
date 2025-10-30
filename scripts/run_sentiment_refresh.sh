#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"

mkdir -p "$LOGDIR" "$REPO/data/sentiment"
cd "$REPO"

/usr/bin/flock -n /tmp/sentiment_refresh.lock bash -lc "
  source '$REPO/.venv/bin/activate'
  cd '$REPO'
  python -m src.fetchers.sentiment_refresh --date last1days --cache false
" >> "$LOGDIR/sentiment_refresh.log" 2>&1
