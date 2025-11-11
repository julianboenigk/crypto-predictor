# src/backtest/rule_based.py
from __future__ import annotations
from typing import List, Dict, Any


def backtest_signals(
    signals: List[Dict[str, Any]],
    long_thr: float = 0.6,
    short_thr: float = -0.6,
    rr: float = 1.5,
    winrate_assumption: float = 0.55,
) -> Dict[str, Any]:
    """
    sehr einfache Auswertung:
    - zählt, wie viele signale überhaupt handelbar gewesen wären
    - nimmt an, dass ein Anteil der Trades TP trifft (winrate_assumption)
    - PnL pro Trade = +1R oder -1R, R:R fließt nicht in echte Preisbewegung ein
      sondern nur in Info
    """

    total = 0
    longs = 0
    shorts = 0
    for sig in signals:
        d = sig.get("decision")
        s = float(sig.get("score", 0.0))
        if d == "LONG" and s >= long_thr:
            total += 1
            longs += 1
        elif d == "SHORT" and s <= short_thr:
            total += 1
            shorts += 1

    # einfache PnL-Schätzung
    wins = int(total * winrate_assumption)
    losses = total - wins

    # wir zählen 1R pro Trade
    pnl_r = wins * 1.0 - losses * 1.0

    return {
        "signals_total": len(signals),
        "trades": total,
        "longs": longs,
        "shorts": shorts,
        "winrate_assumption": winrate_assumption,
        "wins": wins,
        "losses": losses,
        "pnl_r": pnl_r,
        "rr": rr,
    }
