# src/backtest/run_latest.py

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.backtest.data_loader import load_pair_history
from src.backtest.core import simulate_backtest
from src.app.main import load_universe, FINAL_SCORE_MIN
from src.backtest.trade_log import write_backtest_trades

OUT_DIR = "data/backtests"


def run_all(score_min: Optional[float] = None) -> str:
    """
    Führt einen vollständigen Backtest über alle Paare im Universe aus.

    score_min:
        - Wenn None: wird FINAL_SCORE_MIN aus src.app.main verwendet
        - Sonst: explizit übergebener Score-Gate-Wert
    """
    if score_min is None:
        score_min = FINAL_SCORE_MIN

    pairs, interval, _ = load_universe()

    result: Dict[str, Any] = {}
    all_trades = []

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"backtest_{timestamp}.json")

    for pair in pairs:
        candles = load_pair_history(pair, interval)
        bt = simulate_backtest(pair, candles, score_min=float(score_min))
        result[pair] = bt

        # Trades einsammeln
        for t in bt.get("trades", []):
            all_trades.append(t)

    # Backtest-JSON speichern
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print("Backtest saved:", path)

    # JSONL-Trade-Log schreiben
    trades_path = "data/backtests/backtest_trades_latest.jsonl"
    write_backtest_trades(all_trades, trades_path)
    print("Backtest trades saved:", trades_path)

    return path


def main() -> None:
    """
    CLI-Entry: nutzt FINAL_SCORE_MIN als Score-Gate.
    """
    run_all(score_min=None)


if __name__ == "__main__":
    main()