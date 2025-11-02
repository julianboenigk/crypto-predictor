#!/usr/bin/env bash
set -euo pipefail
cd /home/crypto/crypto-predictor
mkdir -p data
ts=$(date -u +%Y-%m-%d_%H-%M-%S)
if [ -f data/cron.log ]; then
  cp data/cron.log "data/cron.$ts.log" || true
  : > data/cron.log
fi
ls -1t data/cron.*.log 2>/dev/null | tail -n +8 | xargs -r rm -f
