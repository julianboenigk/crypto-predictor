# src/backtest/signal_engine.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple, Sequence

from src.agents.technical import TechnicalAgent
from src.agents.base import Candle


# Default-Schwellen für den Backtest, separat von Consensus-Live-Logic
BACKTEST_TECH_LONG = float(os.getenv("BACKTEST_TECH_LONG", os.getenv("TECH_DRIVER_LONG", "0.7")))
BACKTEST_TECH_SHORT = float(os.getenv("BACKTEST_TECH_SHORT", os.getenv("TECH_DRIVER_SHORT", "-0.65")))

# Einen TechnicalAgent einmalig instanzieren
_TECH_AGENT = TechnicalAgent()


def compute_backtest_signal(pair: str, candles: Sequence[Candle]) -> Dict[str, Any]:
    """
    Backtest-Signallogik (v1):
    - nutzt ausschließlich den TechnicalAgent
    - kein LLM, keine News/Sentiment/Research
    - Entscheidung nur auf Basis der Technical-Score-Schwellen

    Rückgabe-Format:
        {
          "pair": str,
          "score": float,
          "decision": "LONG" | "SHORT" | "HOLD",
          "breakdown": [("technical", score, confidence)],
        }
    """

    if not candles:
        return {
            "pair": pair,
            "score": 0.0,
            "decision": "HOLD",
            "breakdown": [],
        }

    # Im Backtest betrachten wir jedes Candle-Fenster als "fresh"
    res = _TECH_AGENT.run(pair, candles, inputs_fresh=True)

    score = float(res.get("score", 0.0))
    conf = float(res.get("confidence", 0.0))

    decision = "HOLD"
    if score >= BACKTEST_TECH_LONG:
        decision = "LONG"
    elif score <= BACKTEST_TECH_SHORT:
        decision = "SHORT"

    breakdown: List[Tuple[str, float, float]] = [
        ("technical", score, conf)
    ]

    return {
        "pair": pair,
        "score": score,
        "decision": decision,
        "breakdown": breakdown,
    }
