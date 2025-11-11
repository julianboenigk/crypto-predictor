# src/backtest/equity.py
from __future__ import annotations
from typing import Dict, Any, List


def build_equity_curve(real_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    curve: List[Dict[str, Any]] = []
    eq = 0.0
    for tr in real_result.get("trades", []):
        if tr["outcome"] == "TP":
            eq += 1.0
        elif tr["outcome"] == "SL":
            eq -= 1.0
        else:
            # unbekannt -> 0
            eq += 0.0
        curve.append(
            {
                "t": tr["t"],
                "pair": tr["pair"],
                "eq": eq,
                "outcome": tr["outcome"],
            }
        )
    return curve
