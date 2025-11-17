# src/reports/backtest_pair_stats.py
from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path
from typing import Any, Dict


def load_latest_backtest() -> Dict[str, Any]:
    files = sorted(glob("data/backtests/backtest_*.json"))
    if not files:
        raise FileNotFoundError("No backtest_*.json files found in data/backtests")
    path = Path(files[-1])
    data = json.loads(path.read_text())
    data["_file"] = path.name
    return data


def compute_pair_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    trades = data.get("trades", [])
    if not trades:
        return {
            "file": data.get("_file"),
            "pairs": {},
            "n_trades_total": 0,
        }

    rr = float(os.getenv("BACKTEST_RR", "1.5"))

    pairs: Dict[str, Dict[str, Any]] = {}
    for t in trades:
        pair = str(t.get("pair", "UNKNOWN"))
        outcome = t.get("outcome")

        if pair not in pairs:
            pairs[pair] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "pnl_r": 0.0,
            }

        stats = pairs[pair]
        stats["trades"] += 1

        if outcome == "TP":
            stats["wins"] += 1
            stats["pnl_r"] += rr
        elif outcome == "SL":
            stats["losses"] += 1
            stats["pnl_r"] -= 1.0
        else:
            # unknown / BE / cancelled -> zählt als Trade, aber 0R
            pass

    # Winrate je Pair berechnen
    for pair, stats in pairs.items():
        n = stats["trades"]
        if n > 0:
            stats["winrate"] = stats["wins"] / n
        else:
            stats["winrate"] = None

    return {
        "file": data.get("_file"),
        "n_trades_total": len(trades),
        "pairs": pairs,
    }


def main() -> None:
    data = load_latest_backtest()
    stats = compute_pair_stats(data)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
