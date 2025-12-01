# src/backtest/core.py

from __future__ import annotations
from typing import List, Dict, Any

from src.backtest.signal_engine import compute_backtest_signal
from src.trade.risk import compute_order_levels


def simulate_backtest(
    pair: str,
    candles: List[Dict[str, Any]],
    score_min: float = 0.0,
    rr: float = 1.5,
    sl_pct: float = 0.004,
    history_len: int = 300,
) -> Dict[str, Any]:
    """
    Kern-Backtest:
    - iteriert über Candles
    - ruft die reine Backtest-Signalengine für jedes Candle auf
      (TechnicalAgent, offline)
    - simuliert SL/TP
    - aggregiert Ergebnisse (R-Multiples)
    """

    trades: List[Dict[str, Any]] = []
    open_trade: Dict[str, Any] | None = None

    # Debug-Zähler
    sig_long = 0
    sig_short = 0
    sig_hold = 0
    opened_trades = 0

    for idx, candle in enumerate(candles):
        price = float(candle["c"])

        # History-Fenster für Signal-Engine bestimmen
        start_idx = max(0, idx - history_len + 1)
        history = candles[start_idx : idx + 1]

        signal = compute_backtest_signal(pair, history)
        score = float(signal.get("score", 0.0))
        decision = str(signal.get("decision", "HOLD"))
        breakdown = signal.get("breakdown", [])

        # Debug-Zähler
        if decision == "LONG":
            sig_long += 1
        elif decision == "SHORT":
            sig_short += 1
        else:
            sig_hold += 1

        # Score-Gate
        if abs(score) < score_min:
            continue

        # Neuer Trade nur, wenn keiner offen ist
        if decision in ("LONG", "SHORT") and open_trade is None:
            ol = compute_order_levels(
                side=decision,
                price=price,
                risk_pct=0.01,
                rr=rr,
                sl_distance_pct=sl_pct,
            )

            open_trade = {
                "pair": pair,
                "side": decision,
                "entry": ol["entry"],
                "stop_loss": ol["stop_loss"],
                "take_profit": ol["take_profit"],
                "entry_idx": idx,
                "entry_ts": candle["t"],
                "entry_score": score,
                "breakdown": breakdown,
            }
            opened_trades += 1
            continue

        # SL/TP Simulation für offenen Trade
        if open_trade is not None:
            low = float(candle["low"])
            high = float(candle["h"])

            if open_trade["side"] == "LONG":
                if low <= open_trade["stop_loss"]:
                    pnl = -1.0
                    exit_price = open_trade["stop_loss"]
                elif high >= open_trade["take_profit"]:
                    pnl = rr
                    exit_price = open_trade["take_profit"]
                else:
                    continue
            else:  # SHORT
                if high >= open_trade["stop_loss"]:
                    pnl = -1.0
                    exit_price = open_trade["stop_loss"]
                elif low <= open_trade["take_profit"]:
                    pnl = rr
                    exit_price = open_trade["take_profit"]
                else:
                    continue

            # Trade schließen
            open_trade["exit_idx"] = idx
            open_trade["exit_ts"] = candle["t"]
            open_trade["exit"] = exit_price
            open_trade["pnl_r"] = pnl
            trades.append(open_trade)
            open_trade = None

    # Debug-Output für dieses Pair
    print(
        f"[BACKTEST] {pair}: signals L/S/H = {sig_long}/{sig_short}/{sig_hold}, "
        f"opened={opened_trades}, closed={len(trades)}"
    )

    # Aggregation
    wins = sum(1 for t in trades if t["pnl_r"] > 0)
    losses = sum(1 for t in trades if t["pnl_r"] < 0)
    n = len(trades)

    if n > 0:
        gross_profit = sum(t["pnl_r"] for t in trades if t["pnl_r"] > 0)
        gross_loss = -sum(t["pnl_r"] for t in trades if t["pnl_r"] < 0)
        pf = gross_profit / gross_loss if gross_loss > 0 else None
        expectancy = sum(t["pnl_r"] for t in trades) / n
        winrate = wins / n
    else:
        pf = expectancy = winrate = None

    return {
        "pair": pair,
        "n_trades": n,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "pf": pf,
        "expectancy": expectancy,
        "trades": trades,
    }
