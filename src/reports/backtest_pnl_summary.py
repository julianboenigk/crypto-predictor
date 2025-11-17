# src/reports/backtest_pnl_summary.py
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


def compute_pnl_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    n_trades = int(data.get("n_trades", 0))
    wins = int(data.get("wins", 0))
    losses = int(data.get("losses", 0))

    if n_trades == 0:
        return {
            "file": data.get("_file"),
            "n_trades": 0,
            "wins": wins,
            "losses": losses,
            "winrate": None,
            "rr": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    rr = float(os.getenv("BACKTEST_RR", "1.5"))

    gross_win_r = wins * rr
    gross_loss_r = losses * 1.0
    pnl_r = gross_win_r - gross_loss_r

    winrate = wins / n_trades
    expectancy_r = (winrate * rr) - ((1 - winrate) * 1.0)

    if gross_loss_r > 0:
        profit_factor = gross_win_r / gross_loss_r
    else:
        profit_factor = None

    return {
        "file": data.get("_file"),
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "rr": rr,
        "pnl_r": pnl_r,
        "expectancy_r": expectancy_r,
        "profit_factor": profit_factor,
    }


def main() -> None:
    data = load_latest_backtest()
    summary = compute_pnl_summary(data)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
