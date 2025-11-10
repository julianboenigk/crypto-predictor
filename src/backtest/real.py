# src/backtest/real.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.backtest.loader import load_runs

try:
    from src.data.binance_client import get_ohlcv
except Exception:
    get_ohlcv = None  # type: ignore


def run_real_backtest(
    path: str = "data/runs.log",
    long_thr: float = 0.6,
    short_thr: float = -0.6,
    lookahead_bars: int = 24,
) -> Dict[str, Any]:
    """
    Nimmt den im Run geloggten last_price als Entry.
    Holt danach (best effort) ein paar weitere Kerzen, um TP/SL zu prüfen.
    Wenn keine Future-Daten vorhanden sind, wird der Trade übersprungen.
    """
    runs = load_runs(path)
    trades: List[Dict[str, Any]] = []

    for run in runs:
        t = run.get("run_at")
        results = run.get("results", [])
        for res in results:
            decision = res.get("decision")
            score = float(res.get("score", 0.0))
            pair = res.get("pair")
            interval = res.get("interval") or "15m"
            entry_price = res.get("last_price")

            if entry_price is None:
                continue

            if decision == "LONG" and score >= long_thr:
                side = "LONG"
            elif decision == "SHORT" and score <= short_thr:
                side = "SHORT"
            else:
                continue

            # levels
            if side == "LONG":
                sl = entry_price * (1.0 - 0.004)
                tp = entry_price + (entry_price - sl) * 1.5
            else:
                sl = entry_price * (1.0 + 0.004)
                tp = entry_price - (sl - entry_price) * 1.5

            # future bars holen
            future = []
            if get_ohlcv is not None:
                try:
                    future = get_ohlcv(pair, interval, limit=lookahead_bars)
                except Exception:
                    future = []

            # wir können nur auswerten, wenn überhaupt bars da sind
            outcome = "UNKNOWN"
            exit_price = entry_price
            for i, k in enumerate(future):
                high = float(k[2])
                low = float(k[3])
                if side == "LONG":
                    if high >= tp:
                        outcome = "TP"
                        exit_price = tp
                        break
                    if low <= sl:
                        outcome = "SL"
                        exit_price = sl
                        break
                else:
                    if low <= tp:
                        outcome = "TP"
                        exit_price = tp
                        break
                    if high >= sl:
                        outcome = "SL"
                        exit_price = sl
                        break

            trades.append(
                {
                    "t": t,
                    "pair": pair,
                    "side": side,
                    "entry": entry_price,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "outcome": outcome,
                    "exit_price": exit_price,
                }
            )

    wins = sum(1 for t in trades if t["outcome"] == "TP")
    losses = sum(1 for t in trades if t["outcome"] == "SL")
    unknown = sum(1 for t in trades if t["outcome"] not in ("TP", "SL"))

    return {
        "n_signals": sum(len(run.get("results", [])) for run in runs),
        "n_trades": len(trades),
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "trades": trades,
    }
