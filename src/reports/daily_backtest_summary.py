# src/reports/daily_backtest_summary.py
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# optional Telegram
try:
    from src.core.notify import send_telegram
except Exception:
    send_telegram = None  # type: ignore

BACKTEST_DIR = Path("data/backtests")


def _latest_backtest_file() -> Optional[Path]:
    if not BACKTEST_DIR.exists():
        return None
    files = sorted(BACKTEST_DIR.glob("backtest_*.json"), reverse=True)
    return files[0] if files else None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_float(x: float) -> str:
    return f"{x:.2f}"


def build_summary(bt: Dict[str, Any]) -> str:
    n_trades = int(bt.get("n_trades", 0))
    wins = int(bt.get("wins", 0))
    losses = int(bt.get("losses", 0))
    unknown = int(bt.get("unknown", 0))
    winrate = (wins / n_trades * 100.0) if n_trades > 0 else 0.0

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "📊 *Daily backtest summary*",
        f"Trades: *{n_trades}* (wins {wins} / losses {losses} / unknown {unknown})",
        f"Winrate: *{_fmt_float(winrate)}%*",
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

    # optional Telegram
    if os.getenv("TELEGRAM_ENABLED", "false").lower() == "true" and send_telegram:
        send_telegram(msg)


if __name__ == "__main__":
    main()
