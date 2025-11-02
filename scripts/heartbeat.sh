#!/usr/bin/env bash
set -euo pipefail
cd /home/crypto/crypto-predictor
set -a; source .env; set +a
/home/crypto/crypto-predictor/.venv/bin/python - <<'PY'
from src.core.notify import send_telegram
send_telegram("Crypto Predictor heartbeat: alive ✅", parse_mode="Markdown")
PY
