# src/backtest/run_latest.py

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from src.backtest.data_loader import load_pair_history
from src.backtest.core import simulate_backtest
from src.app.main import load_universe
from src.backtest.trade_log import write_backtest_trades

OUT_DIR = "data/backtests"


def run_all(score_min: float = 0.0) -> str:
    pairs, interval, _ = load_universe()

    result: Dict[str, Any] = {}
    all_trades = []  # neu

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"backtest_{timestamp}.json")

    for pair in pairs:
        candles = load_pair_history(pair, interval)
        bt = simulate_backtest(pair, candles, score_min=score_min)
        result[pair] = bt

        # Trades einsammeln
        for t in bt.get("trades", []):
            all_trades.append(t)

    # Backtest-JSON speichern
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    print("Backtest saved:", path)

    # JSONL-Trade-Log schreiben
    trades_path = "data/backtests/backtest_trades_latest.jsonl"
    write_backtest_trades(all_trades, trades_path)
    print("Backtest trades saved:", trades_path)

    return path


def main() -> None:
    # hier explizit Score-Gate setzen
    run_all(score_min=0.6)


if __name__ == "__main__":
    main()
