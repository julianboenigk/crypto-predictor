#!/usr/bin/env bash
set -euo pipefail
cd /home/crypto/crypto-predictor

# log header
{
  echo "---- $(date -u '+%Y-%m-%d %H:%M:%S UTC') — main ----"
  echo "whoami: $(whoami)"
} >> data/cron.log

# load env and suppress HOLD alerts
set -a
source .env
export SEND_HOLD=false
set +a

exec /home/crypto/crypto-predictor/.venv/bin/python -u -m src.app.main run >> data/cron.log 2>&1
