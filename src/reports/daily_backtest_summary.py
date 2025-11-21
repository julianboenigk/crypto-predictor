from __future__ import annotations

import json
import os
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List

# .env laden (analog main.py)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception:
    send_telegram = None


# ------------------------------------------------------------
# Hilfsfunktionen (Original unverändert)
# ------------------------------------------------------------

def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


# ------------------------------------------------------------
# NEU: 24h-Auswertung basierend auf Trade-Timestamps
# ------------------------------------------------------------

def _extract_trades(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    trades = data.get("trades")
    if isinstance(trades, list):
        return trades
    return []


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    s = str(raw)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def compute_24h_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    trades = _extract_trades(data)
    if not trades:
        return {
            "n_trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)

    filtered = []
    for tr in trades:
        ts = _parse_ts(tr.get("t") or tr.get("exit_time") or tr.get("time"))
        if ts and ts >= cutoff:
            filtered.append(tr)

    if not filtered:
        return {
            "n_trades": 0,
            "wins": 0,
            "losses": 0,
            "winrate": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    # Outcome-basierte Gewinn-/Verlust-Zählung (kompatibel zu deinen Backtests)
    wins = sum(1 for tr in filtered if tr.get("outcome") == "TP")
    losses = sum(1 for tr in filtered if tr.get("outcome") == "SL")
    n_trades = wins + losses

    # pnl_r aus dem Backtest übernehmen
    pnl_list = []
    for tr in filtered:
        try:
            pnl_list.append(float(tr.get("pnl_r", 0.0)))
        except Exception:
            pnl_list.append(0.0)

    pnl_r = sum(pnl_list)
    winrate = wins / n_trades if n_trades > 0 else None
    expectancy_r = pnl_r / n_trades if n_trades > 0 else None

    gross_win_r = sum(v for v in pnl_list if v > 0)
    gross_loss_r = -sum(v for v in pnl_list if v < 0)
    profit_factor = gross_win_r / gross_loss_r if gross_loss_r > 0 else None

    return {
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pnl_r": pnl_r,
        "expectancy_r": expectancy_r,
        "profit_factor": profit_factor,
    }


# ------------------------------------------------------------
# ORIGINAL für alle Trades + Erweiterung mit summary_24h
# ------------------------------------------------------------

def build_human_summary(
    summary: Dict[str, Any],
    summary_24h: Dict[str, Any] | None = None,
) -> str:

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")

    # Original-Werte
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

    lines = []

    # ---------- ORIGINAL BLOCK ----------
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

    # ---------- NEUER BLOCK: LETZTE 24H ----------
    if summary_24h is not None:
        lines.append("")
        lines.append("Letzte 24h:")
        lines.append(f"- Anzahl Trades: {summary_24h['n_trades']}")
        lines.append(
            f"- Gewinn-Trades: {summary_24h['wins']}, Verlust-Trades: {summary_24h['losses']}"
        )
        lines.append(f"- Trefferquote: {_fmt_pct(summary_24h['winrate'])}")
        lines.append(f"- Ergebnis (24h): {_fmt_float(summary_24h['pnl_r'], 1)} R")
        lines.append(
            f"- Erwartungswert (24h): {_fmt_float(summary_24h['expectancy_r'], 2)} R"
        )
        lines.append(
            f"- Profit Factor (24h): {_fmt_float(summary_24h['profit_factor'], 2)}"
        )

    return "\n".join(lines)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main() -> None:
    data = load_latest_backtest()
    summary_all = compute_pnl_summary(data)
    summary_24h = compute_24h_summary(data)

    print(json.dumps(summary_all, indent=2))

    if (
        send_telegram is not None
        and os.getenv("TELEGRAM_BACKTEST_SUMMARY", "true").lower() == "true"
    ):
        msg = build_human_summary(summary_all, summary_24h)
        if len(msg) > 3500:
            msg = msg[:3400] + "\n\n[gekürzt]"
        send_telegram(msg)


if __name__ == "__main__":
    main()
