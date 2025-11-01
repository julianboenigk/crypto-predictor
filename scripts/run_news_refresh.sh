#!/usr/bin/env bash
set -euo pipefail
umask 002

# === paths ===
REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"
OUTDIR="$REPO/data/news"
LOCK="/tmp/news_refresh.lock"

mkdir -p "$LOGDIR" "$OUTDIR"

# === run under a lock to avoid overlaps ===
/usr/bin/flock -n "$LOCK" bash -lc "
  set -euo pipefail
  cd '$REPO'
  # venv
  source '$REPO/.venv/bin/activate'
  export PYTHONPATH='$REPO'
  # run: allowed date-windows include last5min/10/15/30/45/60, today, yesterday, last7days, last30days, last60days, last90days, yeartodate
  python -m src.fetchers.news_refresh \
    --date-window last60min \
    --items 50 \
    --outdir '$OUTDIR' \
    --cache false
" >> "$LOGDIR/news_refresh.log" 2>&1
