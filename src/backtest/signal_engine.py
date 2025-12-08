# src/backtest/signal_engine.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Sequence

from src.agents.base import Candle, AgentResult
from src.agents.technical import TechnicalAgent


def _run_technical(pair: str, candles: Sequence[Candle]) -> AgentResult | None:
    """
    Führt NUR den TechnicalAgent aus.
    """
    ta = TechnicalAgent()
    try:
        res: AgentResult = ta.run(pair, candles, inputs_fresh=True)
    except Exception:
        return None

    if not isinstance(res, dict):
        return None

    return res


def compute_backtest_signal(
    pair: str,
    candles: Sequence[Candle],
) -> Dict[str, Any]:
    """
    Pure, deterministische Backtest-Signalengine:

    - arbeitet ausschließlich auf den übergebenen Candles
    - nutzt nur den TechnicalAgent
    - Entscheidung: Technical-Score vs. TECH_DRIVER_LONG / TECH_DRIVER_SHORT
    """

    if not candles:
        return {
            "pair": pair,
            "score": 0.0,
            "decision": "HOLD",
            "reason": "no candles",
            "breakdown": [],
        }

    res = _run_technical(pair, candles)
    if res is None:
        return {
            "pair": pair,
            "score": 0.0,
            "decision": "HOLD",
            "reason": "technical agent failed",
            "breakdown": [],
        }

    score = float(res.get("score", 0.0))
    conf = float(res.get("confidence", 0.0))

    long_thr = float(os.getenv("TECH_DRIVER_LONG", "0.7"))
    short_thr = float(os.getenv("TECH_DRIVER_SHORT", "-0.6"))

    if score >= long_thr:
        decision = "LONG"
        reason = f"technical score {score:.3f} >= {long_thr:.3f}"
    elif score <= short_thr:
        decision = "SHORT"
        reason = f"technical score {score:.3f} <= {short_thr:.3f}"
    else:
        decision = "HOLD"
        reason = "no technical edge"

    breakdown: List[tuple] = [("technical", score, conf)]

    return {
        "pair": pair,
        "score": score,
        "decision": decision,
        "reason": reason,
        "breakdown": breakdown,
    }
