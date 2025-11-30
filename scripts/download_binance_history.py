#!/usr/bin/env python3
# scripts/download_binance_history.py

import os
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.data.binance_client import get_ohlcv


OUTDIR = Path("data/historical")
OUTDIR.mkdir(parents=True, exist_ok=True)

# Default 120 Tage
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
INTERVAL = "15m"
DAYS = 120

# Binance 15m-Kerzen pro Tag = 96
KL_PER_DAY = 96
PAGE_LIMIT = 1000   # get_ohlcv limit max


def fetch_pair(pair: str, interval: str, days: int):
    out_file = OUTDIR / f"{pair}_{interval}.jsonl"

    if out_file.exists():
        out_file.unlink()  # neu generieren

    print(f"[INFO] Fetching {pair} {interval} for {days} days...")

    total_needed = days * KL_PER_DAY
    total_fetched = 0

    with out_file.open("a", encoding="utf-8") as f:
        while total_fetched < total_needed:
            batch_size = min(PAGE_LIMIT, total_needed - total_fetched)

            data = get_ohlcv(pair, interval, limit=batch_size, as_dataframe=False)

            if not data or not isinstance(data, list):
                print(f"[WARN] No more data for {pair}. Stopping.")
                break

            # write candles
            for row in data:
                f.write(json.dumps(row) + "\n")

            total_fetched += len(data)
            print(f"[INFO] {pair}: fetched {total_fetched}/{total_needed}")

            # Sanity break — Binance wiederholt Daten
            if len(data) < batch_size:
                print(f"[INFO] {pair}: shorter batch → finished.")
                break

            # Binance API cool-down
            time.sleep(0.4)

    print(f"[OK] Saved → {out_file}")


def main():
    print(f"[INFO] Universe={PAIRS}, interval={INTERVAL}, days={DAYS}")
    for pair in PAIRS:
        fetch_pair(pair, INTERVAL, DAYS)


if __name__ == "__main__":
    main()
