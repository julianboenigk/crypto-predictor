# src/reports/daily_backtest_summary.py
from __future__ import annotations
from src.bootstrap.env import env_debug, PROJECT_ROOT  # noqa: F401

import json
import os
from typing import Dict, Any, List
from datetime import datetime, UTC

# ============================================================
# Environment (cron-safe)
# ============================================================

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception as e:
    print(f"[WARN] Telegram import failed: {e}")
    send_telegram = None  # type: ignore

# ============================================================
# Paths (ABSOLUTE)
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"
BACKTEST_DIR = DATA_DIR / "backtests"
TRADES_PATH = BACKTEST_DIR / "backtest_trades_latest.jsonl"

# ============================================================
# Load executed trades
# ============================================================

def load_trades() -> List[Dict[str, Any]]:
    if not TRADES_PATH.exists():
        print(f"[WARN] Backtest trades file not found: {TRADES_PATH}")
        return []

    trades: List[Dict[str, Any]] = []
    try:
        with TRADES_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trades.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print(f"[WARN] Failed reading {TRADES_PATH}: {e}")
        return []

    return trades

# ============================================================
# Compute summary metrics
# ============================================================

def compute_metrics(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(trades)

    wins = sum(1 for t in trades if float(t.get("pnl_r", 0.0)) > 0)
    losses = sum(1 for t in trades if float(t.get("pnl_r", 0.0)) < 0)
    pnl_r = sum(float(t.get("pnl_r", 0.0)) for t in trades)

    winrate = wins / n if n > 0 else None

    return {
        "n_trades": n,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pnl_r": pnl_r,
    }

# ============================================================
# Main
# ============================================================

def main() -> None:
    trades = load_trades()
    if not trades:
        print("[INFO] No trades found → daily backtest summary skipped")
        return

    metrics = compute_metrics(trades)

    print(json.dumps({
        "run_at": datetime.now(UTC).isoformat(),
        "metrics": metrics,
    }, indent=2))

    if send_telegram is None:
        print("[WARN] Telegram skipped: send_telegram is None")
        return

    if os.getenv("TELEGRAM_BACKTEST_SUMMARY", "true").lower() != "true":
        print("[INFO] Telegram backtest summary disabled via TELEGRAM_BACKTEST_SUMMARY")
        return

    msg = (
        "📊 Daily Backtest Summary\n\n"
        f"Trades: {metrics['n_trades']}\n"
        f"Wins / Losses: {metrics['wins']} / {metrics['losses']}\n"
        f"Winrate: {metrics['winrate']:.1%}\n"
        f"PnL (R): {metrics['pnl_r']:.2f}\n\n"
        f"Updated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
    )

    send_telegram(msg)
    print("[INFO] Daily backtest summary sent via Telegram")


if __name__ == "__main__":
    main()
