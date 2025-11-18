# src/reports/daily_backtest_summary.py
from __future__ import annotations

import json
import os
from datetime import datetime, UTC
from typing import Any, Dict

from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception:
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
    n_trades = summary.get("n_trades", 0)
    wins = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    winrate = summary.get("winrate")

    rr = summary.get("rr")

    pnl_gross = summary.get("pnl_r_gross")
    expectancy_gross = summary.get("expectancy_r_gross")
    profit_factor_gross = summary.get("profit_factor_gross")

    fee_r_per_trade = summary.get("fee_r_per_trade")
    fee_total_r = summary.get("fee_total_r")

    pnl_net = summary.get("pnl_r")
    expectancy_net = summary.get("expectancy_r")
    profit_factor_net = summary.get("profit_factor")

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    lines = []
    lines.append(f"Backtest-Auswertung ({date_str}):")
    lines.append("")
    lines.append(f"- Anzahl der Trades: {n_trades}")
    lines.append(f"- Gewinn-Trades: {wins}, Verlust-Trades: {losses}")
    lines.append(f"- Trefferquote: {_fmt_pct(winrate)}")
    lines.append(f"- Chance-Risiko-Verhältnis (TP/SL): {_fmt_float(rr)} : 1")

    if pnl_gross is not None:
        lines.append(f"- Ergebnis VOR Gebühren: {_fmt_float(pnl_gross, 1)} R")

    if fee_r_per_trade is not None:
        lines.append(f"- Trading-Gebühren: {_fmt_float(fee_r_per_trade, 3)} R pro Trade")
        lines.append(f"  → Gesamtgebühren: {_fmt_float(fee_total_r, 1)} R")

    if pnl_net is not None:
        lines.append(f"- Ergebnis NACH Gebühren: {_fmt_float(pnl_net, 1)} R")

    if expectancy_net is not None:
        lines.append(
            f"- Erwartungswert NACH Gebühren: {_fmt_float(expectancy_net, 2)} R "
            f"(entspricht ~{_fmt_float(expectancy_net * 100, 0)} € pro 100 € Risiko)"
        )

    if profit_factor_net is not None:
        lines.append(
            f"- Profit Factor NACH Gebühren: {_fmt_float(profit_factor_net, 2)} : 1"
        )

    lines.append("")
    lines.append(
        f"Zum Vergleich: VOR Gebühren ~{_fmt_float(expectancy_gross, 2)} R Erwartungswert "
        f"und Profit Factor {_fmt_float(profit_factor_gross, 2)}."
    )

    return "\n".join(lines)


def main() -> None:
    data = load_latest_backtest()
    summary = compute_pnl_summary(data)
    print(json.dumps(summary, indent=2))

    if send_telegram is not None and os.getenv("TELEGRAM_BACKTEST_SUMMARY", "true").lower() == "true":
        msg = build_human_summary(summary)
        if len(msg) > 3500:
            msg = msg[:3400] + "\n\n[gekürzt]"
        send_telegram(msg)


if __name__ == "__main__":
    main()
