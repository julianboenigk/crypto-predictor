#!/usr/bin/env bash
set -euo pipefail

REPO="/home/crypto/crypto-predictor"
cd "$REPO"

# Ensure imports work and env vars are exported for the shell too
export PYTHONPATH="$REPO"
set -a; [ -f "$REPO/.env" ] && . "$REPO/.env"; set +a

source .venv/bin/activate
exec /usr/bin/flock -n /tmp/main_run.lock \
  "$REPO/.venv/bin/python" -m src.app.main run \
  >> data/logs/main.log 2>&1
