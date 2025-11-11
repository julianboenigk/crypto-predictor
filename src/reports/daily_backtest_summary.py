# src/reports/daily_backtest_summary.py
from __future__ import annotations

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional

from src.core.timeutil import fmt_local

try:
    from src.core.notify import send_telegram, send_telegram_photo
except Exception:
    send_telegram = None  # type: ignore
    send_telegram_photo = None  # type: ignore

BACKTEST_DIR = Path("data/backtests")
EQUITY_PNG = Path("data/reports/equity_latest.png")


def _latest_backtest_file() -> Optional[Path]:
    if not BACKTEST_DIR.exists():
        return None
    files = sorted(BACKTEST_DIR.glob("backtest_*.json"), reverse=True)
    return files[0] if files else None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_summary(bt: Dict[str, Any]) -> str:
    n_trades = int(bt.get("n_trades", 0))
    wins = int(bt.get("wins", 0))
    losses = int(bt.get("losses", 0))
    unknown = int(bt.get("unknown", 0))
    winrate = (wins / n_trades * 100.0) if n_trades > 0 else 0.0

    ts = fmt_local()

    lines = [
        "📊 *Daily backtest summary*",
        f"Trades: *{n_trades}* (wins {wins} / losses {losses} / unknown {unknown})",
        f"Winrate: *{winrate:.2f}%*",
        "",
        f"_generated at {ts}_",
    ]
    return "\n".join(lines)


def main() -> None:
    latest = _latest_backtest_file()
    if latest is None:
        print("no backtest files found")
        return

    bt = _load_json(latest)
    msg = build_summary(bt)
    print(msg)

    enabled = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

    if enabled and send_telegram:
        ok1 = send_telegram(msg)
        print(f"telegram_sent={ok1}")

        # falls ein Equity-Plot existiert, mitschicken
        if EQUITY_PNG.exists() and send_telegram_photo:
            ok2 = send_telegram_photo(str(EQUITY_PNG), caption="📈 Equity curve (latest backtest)")
            print(f"telegram_photo_sent={ok2}")
        else:
            print("no equity plot found to send")
    else:
        print("telegram_send_skipped")


if __name__ == "__main__":
    main()
