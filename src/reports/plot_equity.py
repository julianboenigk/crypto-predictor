# src/reports/plot_equity.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore

DATA_DIR = Path("data")
BACKTEST_DIR = DATA_DIR / "backtests"
REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _latest_backtest() -> Dict[str, Any] | None:
    if not BACKTEST_DIR.exists():
        print("no backtest directory (data/backtests) found")
        return None
    files = sorted(BACKTEST_DIR.glob("backtest_*.json"), reverse=True)
    if not files:
        print("no backtest_*.json files found in data/backtests")
        return None
    latest = files[0]
    return json.loads(latest.read_text(encoding="utf-8"))


def _build_equity(trades: List[Dict[str, Any]]) -> List[float]:
    eq: List[float] = []
    cur = 0.0
    for tr in trades:
        outcome = tr.get("outcome")
        if outcome == "TP":
            cur += 1.0
        elif outcome == "SL":
            cur -= 1.0
        else:
            cur += 0.0
        eq.append(cur)
    return eq


def main() -> None:
    bt = _latest_backtest()
    if bt is None:
        return

    trades = bt.get("trades", [])
    if not trades:
        print("no trades in latest backtest")
        return

    equity = _build_equity(trades)

    plt.figure(figsize=(10, 4))
    plt.plot(equity, linewidth=1.5)
    plt.title("Equity curve (latest backtest)")
    plt.xlabel("trade #")
    plt.ylabel("R")
    plt.grid(True, linestyle=":", linewidth=0.5)

    out_path = REPORT_DIR / "equity_latest.png"
    plt.tight_layout()
    plt.savefig(out_path)
    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
