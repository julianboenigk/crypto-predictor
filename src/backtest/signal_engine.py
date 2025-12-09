# src/backtest/signal_engine.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Sequence

from src.agents.base import Candle, AgentResult
from src.agents.technical import TechnicalAgent
from src.agents.sentiment import SentimentAgent
from src.agents.news import NewsAgent
from src.agents.research import ResearchAgent


def _run_agent(agent_cls, pair: str, candles: Sequence[Candle]) -> AgentResult | None:
    """
    Runs an agent safely and returns a normalized AgentResult or None.
    """
    try:
        a = agent_cls()
        res: AgentResult = a.run(pair, candles, inputs_fresh=True)
        if not isinstance(res, dict):
            return None
        if "score" not in res:
            return None
        return {
            "score": float(res.get("score", 0.0)),
            "confidence": float(res.get("confidence", 1.0)),
        }
    except Exception:
        return None


def compute_backtest_signal(
    pair: str,
    candles: Sequence[Candle],
) -> Dict[str, Any]:
    """
    Deterministic Backtest-Signalengine – jetzt mit ALLEN Agents:

    - Technical baseline
    - Sentiment
    - News
    - Research

    Es wird weiterhin NUR der Technical-Score für LONG/SHORT verwendet
    (der Backtest muss deterministisch und "pure" bleiben),
    aber wir loggen ALLE agent_outputs für spätere Analysen.
    """

    if not candles:
        return {
            "pair": pair,
            "score": 0.0,
            "decision": "HOLD",
            "reason": "no candles",
            "agent_outputs": {},
            "breakdown": [],
        }

    # ---- RUN TECHNICAL (REQUIRED) ----
    tech = _run_agent(TechnicalAgent, pair, candles)
    if tech is None:
        return {
            "pair": pair,
            "score": 0.0,
            "decision": "HOLD",
            "reason": "technical agent failed",
            "agent_outputs": {},
            "breakdown": [],
        }

    technical_score = tech["score"]
    technical_conf = tech["confidence"]

    # ---- RUN OPTIONAL AGENTS ----
    sentiment = _run_agent(SentimentAgent, pair, candles)
    news = _run_agent(NewsAgent, pair, candles)
    research = _run_agent(ResearchAgent, pair, candles)

    agent_outputs = {
        "technical": tech,
        "sentiment": sentiment or {"score": 0.0, "confidence": 0.0},
        "news": news or {"score": 0.0, "confidence": 0.0},
        "research": research or {"score": 0.0, "confidence": 0.0},
    }

    # ---- DECISION BASED ONLY ON TECHNICAL ----
    long_thr = float(os.getenv("TECH_DRIVER_LONG", "0.7"))
    short_thr = float(os.getenv("TECH_DRIVER_SHORT", "-0.65"))

    if technical_score >= long_thr:
        decision = "LONG"
        reason = f"technical score {technical_score:.3f} >= {long_thr:.3f}"
    elif technical_score <= short_thr:
        decision = "SHORT"
        reason = f"technical score {technical_score:.3f} <= {short_thr:.3f}"
    else:
        decision = "HOLD"
        reason = "no technical edge"

    breakdown: List[tuple] = [
        ("technical", technical_score, technical_conf),
        ("sentiment", agent_outputs["sentiment"]["score"], agent_outputs["sentiment"]["confidence"]),
        ("news", agent_outputs["news"]["score"], agent_outputs["news"]["confidence"]),
        ("research", agent_outputs["research"]["score"], agent_outputs["research"]["confidence"]),
    ]

    # ---- FINAL OUTPUT ----
    return {
        "pair": pair,
        "score": technical_score,      # system uses technical score for direction
        "decision": decision,
        "reason": reason,
        "agent_outputs": agent_outputs,
        "breakdown": breakdown,
    }
