#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
LOGDIR="$REPO/data/logs"
ARCHIVE="$LOGDIR/archive"

mkdir -p "$ARCHIVE"

# 1️⃣ Compress yesterday’s logs (skip already compressed)
find "$LOGDIR" -maxdepth 1 -type f -name "*.log" ! -name "*.gz" -mtime +1 -print0 | while IFS= read -r -d '' f; do
  gzip -9 "$f" && mv "$f.gz" "$ARCHIVE/" || true
done

# 2️⃣ Keep only 30 days of archives
find "$ARCHIVE" -type f -name "*.gz" -mtime +30 -delete

# 3️⃣ Prune old CSV data (>90 days)
find "$REPO/data" -type f -name "*.csv" -mtime +90 -delete

# 4️⃣ Record summary
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleanup done" >> "$LOGDIR/cleanup.log"
