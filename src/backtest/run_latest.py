# src/backtest/run_latest.py

from __future__ import annotations
import json
import os
from datetime import datetime, timezone

from src.backtest.data_loader import load_pair_history
from src.backtest.core import simulate_backtest
from src.app.main import load_universe

OUT_DIR = "data/backtests"


def run_all(score_min: float = 0.0):
    pairs, interval, _ = load_universe()

    result = {}
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = f"{OUT_DIR}/backtest_{timestamp}.json"

    for pair in pairs:
        candles = load_pair_history(pair, interval)
        bt = simulate_backtest(pair, candles, score_min=score_min)
        result[pair] = bt

    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    print("Backtest saved:", path)
    return path


if __name__ == "__main__":
    run_all(score_min=0.0)
