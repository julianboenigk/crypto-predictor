# src/reports/backtest_time_slices.py
from __future__ import annotations

import json
import os
from glob import glob
from pathlib import Path
from typing import Any, Dict, List


def load_latest_backtest() -> Dict[str, Any]:
    files = sorted(glob("data/backtests/backtest_*.json"))
    if not files:
        raise FileNotFoundError("No backtest_*.json files found in data/backtests")
    path = Path(files[-1])
    data = json.loads(path.read_text())
    data["_file"] = path.name
    return data


def _slice_trades(trades: List[Dict[str, Any]], n_slices: int = 3) -> List[List[Dict[str, Any]]]:
    n = len(trades)
    if n == 0 or n_slices <= 1:
        return [trades]

    slice_size = max(1, n // n_slices)
    slices: List[List[Dict[str, Any]]] = []
    start = 0
    for i in range(n_slices - 1):
        end = start + slice_size
        slices.append(trades[start:end])
        start = end
    slices.append(trades[start:])
    return slices


def _compute_slice_stats(trades: List[Dict[str, Any]], rr: float) -> Dict[str, Any]:
    n = len(trades)
    wins = 0
    losses = 0
    pnl_r = 0.0

    for t in trades:
        outcome = t.get("outcome")
        if outcome == "TP":
            wins += 1
            pnl_r += rr
        elif outcome == "SL":
            losses += 1
            pnl_r -= 1.0

    winrate = wins / n if n > 0 else None
    return {
        "n_trades": n,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pnl_r": pnl_r,
    }


def compute_time_slices(data: Dict[str, Any]) -> Dict[str, Any]:
    trades: List[Dict[str, Any]] = data.get("trades", [])
    rr = float(os.getenv("BACKTEST_RR", "1.5"))

    slices = _slice_trades(trades, n_slices=3)
    labels = ["early", "mid", "late"]

    out: Dict[str, Any] = {
        "file": data.get("_file"),
        "n_trades_total": len(trades),
        "slices": {},
    }

    for label, s_trades in zip(labels, slices):
        out["slices"][label] = _compute_slice_stats(s_trades, rr)

    return out


def main() -> None:
    data = load_latest_backtest()
    stats = compute_time_slices(data)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
