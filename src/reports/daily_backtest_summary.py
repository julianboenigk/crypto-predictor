# src/reports/daily_backtest_summary.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

# Telegram sender (same as daily_live_summary)
try:
    from src.core.notify import send_telegram  # type: ignore
except Exception:
    send_telegram = None  # type: ignore


# ------------------------------------------------------------------
# Paths (single source of truth)
# ------------------------------------------------------------------
DATA_DIR = Path("data")
BACKTEST_DIR = DATA_DIR / "backtests"
TRADES_PATH = BACKTEST_DIR / "backtest_trades_latest.jsonl"


# ------------------------------------------------------------------
# Load executed trades
# ------------------------------------------------------------------
def load_trades() -> List[Dict[str, Any]]:
    if not TRADES_PATH.exists():
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
# Compute summary metrics
# ------------------------------------------------------------------
def compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(trades)
    wins = sum(1 for t in trades if float(t.get("pnl_r", 0.0)) > 0)
    losses = sum(1 for t in trades if float(t.get("pnl_r", 0.0)) < 0)
    pnl_r = sum(float(t.get("pnl_r", 0.0)) for t in trades)

    winrate = wins / n if n > 0 else 0.0

    return {
        "n_trades": n,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pnl_r": pnl_r,
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main() -> None:
    if send_telegram is None:
        print("telegram sender unavailable")
        return

    trades = load_trades()
    if not trades:
        print("no executed trades found for daily summary")
        return

    m = compute_metrics(trades)

    msg = (
        "📊 *Daily Backtest Summary*\n\n"
        f"Trades: {m['n_trades']}\n"
        f"Wins / Losses: {m['wins']} / {m['losses']}\n"
        f"Winrate: {m['winrate']:.1%}\n"
        f"PnL (R): {m['pnl_r']:.2f}\n\n"
        f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    send_telegram(msg)
    print("daily backtest summary sent")


if __name__ == "__main__":
    main()
