# src/trade/risk.py
from __future__ import annotations
from typing import Dict, Any


def compute_order_levels(
    side: str,
    price: float,
    risk_pct: float = 0.01,
    rr: float = 1.5,
    sl_distance_pct: float = 0.004,
) -> Dict[str, Any]:
    """
    side: "LONG" oder "SHORT"
    price: aktueller Marktpreis
    risk_pct: Anteil vom Konto, der max. verloren werden darf (wird erst im Live-Mode gebraucht)
    rr: gewünschtes Chance/Risiko-Verhältnis
    sl_distance_pct: wie weit SL vom Entry weg liegt (0.004 = 0.4%)

    return: dict mit entry, stop, take_profit
    """
    side = side.upper()
    if side not in ("LONG", "SHORT"):
        raise ValueError("side must be LONG or SHORT")

    if side == "LONG":
        entry = price
        stop = price * (1.0 - sl_distance_pct)
        tp = entry + (entry - stop) * rr
    else:  # SHORT
        entry = price
        stop = price * (1.0 + sl_distance_pct)
        tp = entry - (stop - entry) * rr

    return {
        "side": side,
        "entry": round(entry, 6),
        "stop_loss": round(stop, 6),
        "take_profit": round(tp, 6),
        "risk_pct": risk_pct,
        "rr": rr,
    }
