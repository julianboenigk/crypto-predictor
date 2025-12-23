# src/reports/plot_equity.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # type: ignore


# ------------------------------------------------------------------
# Paths (single source of truth)
# ------------------------------------------------------------------
DATA_DIR = Path("data")
BACKTEST_DIR = DATA_DIR / "backtests"
TRADES_PATH = BACKTEST_DIR / "backtest_trades_latest.jsonl"
REPORT_DIR = DATA_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------------
# Load executed trades
# ------------------------------------------------------------------
def _load_trades() -> List[Dict[str, Any]]:
    if not TRADES_PATH.exists():
        print(f"missing trades file: {TRADES_PATH}")
        return []

    trades: List[Dict[str, Any]] = []
    with TRADES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trades.append(json.loads(line))
            except Exception:
                continue

    return trades


# ------------------------------------------------------------------
# Build equity in R units
# ------------------------------------------------------------------
def _build_equity(trades: List[Dict[str, Any]]) -> List[float]:
    eq: List[float] = []
    cur = 0.0

    for tr in trades:
        pnl_r = tr.get("pnl_r")
        if isinstance(pnl_r, (int, float)):
            cur += float(pnl_r)
        else:
            # fallback if pnl_r missing
            outcome = tr.get("outcome")
            if outcome == "TP":
                cur += 1.0
            elif outcome == "SL":
                cur -= 1.0

        eq.append(cur)

    return eq


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main() -> None:
    trades = _load_trades()
    if not trades:
        print("no trades found for equity plot")
        return

    equity = _build_equity(trades)

    plt.figure(figsize=(10, 4))
    plt.plot(equity, linewidth=1.5)
    plt.title("Equity curve (executed trades)")
    plt.xlabel("trade #")
    plt.ylabel("R")
    plt.grid(True, linestyle=":", linewidth=0.5)

    out_path = REPORT_DIR / "equity_latest.png"
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()

    print(f"saved: {out_path}")


if __name__ == "__main__":
    main()
