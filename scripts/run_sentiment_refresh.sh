#!/usr/bin/env bash
set -euo pipefail
umask 002

# === paths ===
REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"
OUTDIR="$REPO/data/sentiment"
LOCK="/tmp/sentiment_refresh.lock"

mkdir -p "$LOGDIR" "$OUTDIR"

# === run under a lock to avoid overlaps ===
/usr/bin/flock -n "$LOCK" bash -lc "
  set -euo pipefail
  cd '$REPO'
  # venv
  source '$REPO/.venv/bin/activate'
  export PYTHONPATH='$REPO'
  # 'yesterday' is valid for the provider's /stat endpoint
  python -m src.fetchers.sentiment_refresh \
    --date-window yesterday \
    --outdir '$OUTDIR' \
    --cache false
" >> "$LOGDIR/sentiment_refresh.log" 2>&1
