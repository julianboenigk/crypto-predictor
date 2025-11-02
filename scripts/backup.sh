#!/usr/bin/env bash
set -euo pipefail
cd /home/crypto/crypto-predictor
mkdir -p backups
ts=$(date -u +%Y-%m-%d_%H-%M-%S)
tar --exclude='.venv' --exclude='__pycache__' --exclude='backups' --exclude='.git' \
    -czf "backups/crypto-predictor_$ts.tgz" src configs data pyproject.toml .env || true
ls -1t backups/crypto-predictor_*.tgz | tail -n +5 | xargs -r rm -f
