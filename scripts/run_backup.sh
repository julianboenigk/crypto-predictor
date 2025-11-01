#!/usr/bin/env bash
set -euo pipefail
umask 002

REPO="/home/crypto/crypto-predictor"
BACKUP_DIR="$REPO/data/backups"
LOGDIR="$REPO/data/logs"
LOCKFILE="/tmp/backup_weekly.lock"

mkdir -p "$BACKUP_DIR" "$LOGDIR"

# Timestamp (UTC) for consistent ordering
TS="$(date -u +'%Y%m%dT%H%M%SZ')"
ARCHIVE_TMP="$BACKUP_DIR/backup-$TS.tmp.tar"
ARCHIVE="$BACKUP_DIR/backup-$TS.tar.gz"
LOGFILE="$LOGDIR/backup.log"

(
  flock -n 9 || { echo "[$(date -u +'%F %T')] Another backup is running, exiting." >> "$LOGFILE"; exit 0; }

  echo "[$(date -u +'%F %T')] START backup $ARCHIVE" >> "$LOGFILE"

  cd "$REPO"

  # Collect targets:
  #  - Any .db files in repo root
  #  - data/ directory (CSV/JSON/signals/logs)
  # Excludes huge archives & backups themselves when archiving data/
  TAR_INCLUDE=()
  if ls *.db >/dev/null 2>&1; then
    TAR_INCLUDE+=($(ls *.db))
  fi
  TAR_INCLUDE+=("data")

  # Create uncompressed tar first (faster, safer), then gzip
  tar --exclude='data/backups' \
      --exclude='data/logs/archive' \
      --exclude='data/*.tar' \
      --exclude='data/*.tar.gz' \
      -cf "$ARCHIVE_TMP" "${TAR_INCLUDE[@]}"

  gzip -9 "$ARCHIVE_TMP"
  mv "$ARCHIVE_TMP.gz" "$ARCHIVE"

  # Rotate: keep latest 4 backups, delete the rest
  # (List newest first, skip first 4 lines, delete the rest)
  ls -1t "$BACKUP_DIR"/backup-*.tar.gz 2>/dev/null | tail -n +5 | while read -r old; do
    rm -f "$old"
  done

  echo "[$(date -u +'%F %T')] DONE  backup $ARCHIVE" >> "$LOGFILE"
) 9>"$LOCKFILE"
