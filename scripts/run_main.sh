#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Main orchestrator: runs src.app.main (consensus pipeline).
# Executes inside venv, logs output, and prevents overlap with flock.
# -----------------------------------------------------------------------------
set -euo pipefail
umask 002

# === paths ===
REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"
LOCK="/tmp/main_run.lock"

mkdir -p "$LOGDIR"
cd "$REPO"

# === execute inside virtual environment ===
/usr/bin/flock -n "$LOCK" bash -lc "
  set -euo pipefail
  cd '$REPO'
  source '$REPO/.venv/bin/activate'
  export PYTHONPATH='$REPO'
  # run the consensus/decision loop once
  python -m src.app.main run
" >> "$LOGDIR/main.log" 2>&1
