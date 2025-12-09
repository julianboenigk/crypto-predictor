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
    Erweitert um:
    - agent_outputs  (vollständiger Agent-Output pro Candle)
    """

    with open(path, "w") as f:
        for t in trades:

            # Agent outputs optional aus trade übernehmen
            agent_outputs = t.get("agent_outputs", [])

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

                # NEU: vollständige Agent-Outputs speichern
                "agent_outputs": agent_outputs,

                "meta": {
                    "entry_score": t.get("entry_score"),
                    "breakdown": t.get("breakdown", []),
                    "source": "backtest",
                },
            }

            f.write(json.dumps(line) + "\n")

    return path
