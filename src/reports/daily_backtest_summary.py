# src/reports/daily_backtest_summary.py
from __future__ import annotations

import json
import os
from datetime import datetime, UTC
from typing import Any, Dict

from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception:  # pragma: no cover
    send_telegram = None  # type: ignore


def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def build_human_summary(summary: Dict[str, Any]) -> str:
    """
    Baue eine verständliche, nicht-technische Zusammenfassung
    für Telegram.
    """
    n_trades = summary.get("n_trades", 0)
    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    winrate = summary.get("winrate")
    rr = summary.get("rr")
    pnl_r = summary.get("pnl_r")
    expectancy_r = summary.get("expectancy_r")
    profit_factor = summary.get("profit_factor")

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    lines = []
    lines.append(f"Backtest-Auswertung ({date_str}):")
    lines.append("")
    lines.append(f"- Anzahl der Trades: {n_trades}")
    lines.append(f"- Gewinn-Trades: {wins}, Verlust-Trades: {losses}")
    lines.append(f"- Trefferquote: {_fmt_pct(winrate)}")

    if rr is not None:
        lines.append(f"- Chance-Risiko-Verhältnis pro Trade (TP/SL): ca. {_fmt_float(rr)} : 1")

    if pnl_r is not None:
        lines.append(
            f"- Gesamt-Ergebnis im Backtest: ca. {_fmt_float(pnl_r, 1)} 'R' "
            "(ein 'R' entspricht deinem Risiko pro Trade, z.B. Abstand zwischen Einstieg und Stop-Loss)."
        )

    if expectancy_r is not None:
        lines.append(
            f"- Durchschnittliches Ergebnis pro Trade: ca. {_fmt_float(expectancy_r, 2)} R "
            "(also z.B. bei 100 € Risiko pro Trade ≈ "
            f"{_fmt_float(expectancy_r * 100, 0)} € Gewinn im Schnitt)."
        )

    if profit_factor is not None:
        lines.append(
            f"- Verhältnis aller Gewinne zu allen Verlusten: ca. {_fmt_float(profit_factor, 2)} : 1 "
            "(je höher, desto stabiler die Strategie)."
        )

    return "\n".join(lines)


def main() -> None:
    data = load_latest_backtest()
    summary = compute_pnl_summary(data)

    # JSON-Ausgabe für Logs / Files
    print(json.dumps(summary, indent=2))

    # Optional: Telegram-Nachricht
    if send_telegram is not None and os.getenv("TELEGRAM_BACKTEST_SUMMARY", "true").lower() == "true":
        msg = build_human_summary(summary)
        # Telegram-Limit absichern
        if len(msg) > 3500:
            msg = msg[:3400] + "\n\n[gekürzt]"
        send_telegram(msg)


if __name__ == "__main__":
    main()
