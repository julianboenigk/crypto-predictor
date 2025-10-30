#!/usr/bin/env bash
set -euo pipefail
cd /home/crypto/crypto-predictor
export PYTHONPATH=/home/crypto/crypto-predictor
source .venv/bin/activate
exec /usr/bin/flock -n /tmp/main_run.lock \
  /home/crypto/crypto-predictor/.venv/bin/python -m src.app.main run \
  >> data/logs/main.log 2>&1
