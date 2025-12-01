# src/backtest/core.py
from __future__ import annotations

from typing import List, Dict, Any

from src.app.main import run_once  # nutzt deine bestehende Signal-Engine
from src.trade.risk import compute_order_levels  # gleiche Risk-Logik wie live


def simulate_backtest(
    pair: str,
    candles: List[Dict[str, Any]],
    score_min: float = 0.0,
    rr: float = 1.5,
    sl_pct: float = 0.004,
) -> Dict[str, Any]:
    """
    Kern-Backtest:
    - iteriert über Candles
    - ruft main.run_once() für jedes Candle auf (im backtest_mode)
    - simuliert SL/TP über compute_order_levels
    - aggregiert Ergebnisse in R (Risk-Multiples)
    """

    trades: List[Dict[str, Any]] = []
    open_trade: Dict[str, Any] | None = None

    for idx, candle in enumerate(candles):
        # Erwartetes Candle-Format:
        # {
        #   "t": ...,
        #   "o": ...,
        #   "h": ...,
        #   "low": ...,
        #   "c": ...,
        #   "v": ...
        # }
        price = float(candle["c"])

        # -------------------------------------------------
        # 1) Signal-Engine für dieses Candle ausführen
        # -------------------------------------------------
        # WICHTIG: backtest_mode=True, damit keine Paper-Trades,
        # keine echten Orders und keine Telegram-Nachrichten ausgelöst werden.
        results = run_once(
            single_pair=pair,
            override_price=price,
            backtest_mode=True,
        )

        if not results:
            continue

        # Da wir single_pair verwenden, kommt genau ein Ergebnis zurück
        res = results[0]

        score = float(res.get("score", 0.0))
        decision = str(res.get("decision") or "HOLD").upper()
        breakdown = res.get("breakdown", [])

        # -------------------------------------------------
        # Score-Filter (optional, zusätzlicher Threshold)
        # -------------------------------------------------
        if abs(score) < score_min:
            continue

        # -------------------------------------------------
        # Neue Position eröffnen, wenn flat und LONG/SHORT
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
                "entry_ts": candle.get("t"),
                "entry_score": score,
                "breakdown": breakdown,
            }

            # Nächstes Candle, SL/TP wird weiter unten simuliert
            continue

        # -------------------------------------------------
        # Falls keine offene Position: nichts zu managen
        # -------------------------------------------------
        if open_trade is None:
            continue

        # -------------------------------------------------
        # SL/TP Simulation auf Basis High/Low des Candles
        # -------------------------------------------------
        low = float(candle["low"])
        high = float(candle["h"])

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

        # -------------------------------------------------
        # Trade schließen und speichern
        # -------------------------------------------------
        open_trade["exit_idx"] = idx
        open_trade["exit_ts"] = candle.get("t")
        open_trade["exit"] = float(exit_price)
        open_trade["pnl_r"] = float(pnl)

        trades.append(open_trade)
        open_trade = None

    # -------------------------------------------------
    # Aggregation der Ergebnisse
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
        pf = None
        expectancy = None
        winrate = None

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
