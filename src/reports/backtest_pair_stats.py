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
    """
    Aggregiert Pair-Stats aus einem Backtest-JSON.

    Unterstützt zwei Varianten:
    - Top-Level "trades": Liste aller Trades
    - oder Pair-basierte Struktur: data[pair]["trades"]
    """

    trades = data.get("trades", [])

    # Falls oben keine Trades: aus den Pair-Einträgen zusammensammeln
    if not trades:
        collected = []
        for key, val in data.items():
            if not isinstance(val, dict):
                continue
            pair_trades = val.get("trades")
            if not pair_trades:
                continue
            for t in pair_trades:
                t_copy = dict(t)
                # outcome aus pnl_r ableiten, falls nicht gesetzt
                if "outcome" not in t_copy:
                    pnl = t_copy.get("pnl_r")
                    if pnl is not None:
                        try:
                            pnl_f = float(pnl)
                        except (TypeError, ValueError):
                            pnl_f = 0.0
                        if pnl_f > 0:
                            t_copy["outcome"] = "TP"
                        elif pnl_f < 0:
                            t_copy["outcome"] = "SL"
                        else:
                            t_copy["outcome"] = "BE"
                collected.append(t_copy)

        trades = collected

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

    # Winrate je Pair
    for pair, stats in pairs.items():
        n = stats["trades"]
        stats["winrate"] = stats["wins"] / n if n > 0 else None

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
