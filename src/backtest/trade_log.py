# src/backtest/trade_log.py

from __future__ import annotations

import json
from typing import Any, Dict, Iterable


def write_backtest_trades(
    trades: Iterable[Dict[str, Any]],
    path: str = "data/backtests/backtest_trades_latest.jsonl",
) -> str:
    """
    Schreibt Backtest-Trades als JSONL.
    Format grob kompatibel zu paper_trades_closed.jsonl:

    - pair, side
    - entry_time, exit_time
    - entry_price, exit_price, stop_loss, take_profit
    - pnl_r
    - meta.entry_score, meta.breakdown, meta.source="backtest"
    """
    with open(path, "w") as f:
        for t in trades:
            line = {
                "pair": t.get("pair"),
                "side": t.get("side"),
                "entry_time": t.get("entry_ts"),
                "exit_time": t.get("exit_ts"),
                "entry_price": t.get("entry"),
                "exit_price": t.get("exit"),
                "stop_loss": t.get("stop_loss"),
                "take_profit": t.get("take_profit"),
                "pnl_r": t.get("pnl_r"),
                "meta": {
                    "entry_score": t.get("entry_score"),
                    "breakdown": t.get("breakdown", []),
                    "source": "backtest",
                },
            }
            f.write(json.dumps(line) + "\n")

    return path
