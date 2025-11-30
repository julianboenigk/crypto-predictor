# src/backtest/core.py

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import time

from src.app.main import run_once  # nutzt existierende Signal-Engine
from src.trade.risk import compute_order_levels


def simulate_backtest(pair: str, candles: List[Dict[str, Any]],
                      score_min: float = 0.0,
                      rr: float = 1.5,
                      sl_pct: float = 0.004) -> Dict[str, Any]:

    """
    Kern-Backtest:
    - Iteriert über Candles
    - ruft main.run_once() für jedes Candle auf
    - simuliert SL/TP
    - aggregiert Ergebnisse
    """

    trades = []
    open_trade = None

    for idx, candle in enumerate(candles):
        price = candle["c"]

        # -------------------------------------------------
        # 1) Run signal engine (calls all agents)
        # -------------------------------------------------
        results = run_once(single_pair=pair, override_price=price)

        if not results:
            continue

        res = results[0]  # single pair execution

        score = res["score"]
        decision = res["decision"]
        breakdown = res["breakdown"]

        # -------------------------------------------------
        # Score-Gate
        # -------------------------------------------------
        if abs(score) < score_min:
            continue

        # -------------------------------------------------
        # Order-Levels (wenn LONG / SHORT)
        # -------------------------------------------------
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

            continue

        # -------------------------------------------------
        # SL/TP Simulation
        # -------------------------------------------------
        if open_trade:
            low = candle["l"]
            high = candle["h"]

            # LONG
            if open_trade["side"] == "LONG":
                if low <= open_trade["stop_loss"]:
                    pnl = -1.0
                    exit_price = open_trade["stop_loss"]
                elif high >= open_trade["take_profit"]:
                    pnl = rr
                    exit_price = open_trade["take_profit"]
                else:
                    continue

            # SHORT
            else:
                if high >= open_trade["stop_loss"]:
                    pnl = -1.0
                    exit_price = open_trade["stop_loss"]
                elif low <= open_trade["take_profit"]:
                    pnl = rr
                    exit_price = open_trade["take_profit"]
                else:
                    continue

            # Closed trade
            open_trade["exit_idx"] = idx
            open_trade["exit_ts"] = candle["t"]
            open_trade["exit"] = exit_price
            open_trade["pnl_r"] = pnl
            trades.append(open_trade)
            open_trade = None

    # -------------------------------------------------
    # Aggregation
    # -------------------------------------------------
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
