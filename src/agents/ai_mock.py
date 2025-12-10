# src/agents/ai_mock.py
from __future__ import annotations

import hashlib
import random
from typing import Dict, Any, Sequence
from src.agents.base import Candle


def stable_hash(s: str) -> int:
    """Stable deterministic hash for reproducible mock behavior."""
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def mock_score_from_history(agent: str, pair: str, candles: Sequence[Candle]) -> Dict[str, Any]:
    """
    Deterministic, repeatable mock for AI agents during backtests.
    Score basiert auf Hash des letzten Candles + Agentname,
    damit Candle-basierte Muster zu realistischen Scores führen.
    """

    if not candles:
        return {"score": 0.0, "confidence": 0.3, "explanation": "no data (mock)"}

    last = candles[-1]
    base_str = f"{agent}:{pair}:{last['c']}:{last['low']}:{last['h']}:{last['t']}"

    seed = stable_hash(base_str)
    random.seed(seed)

    # Score ~ -0.5 bis +0.5 — realistische AI-Modulation
    score = random.uniform(-0.5, 0.5)

    # Confidence ~ 0.4 bis 0.9
    conf = random.uniform(0.4, 0.9)

    return {
        "score": float(score),
        "confidence": float(conf),
        "explanation": f"mock-score seed={seed}",
    }
