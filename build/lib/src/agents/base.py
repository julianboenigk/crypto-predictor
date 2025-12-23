# src/agents/base.py

"""
Legacy placeholder – Technical Agent nutzt keine gemeinsame Base mehr.
AI Agents nutzen die neue AIAgent Base (see src/agents/ai_base.py).
Kein echter Code notwendig. Datei bleibt für Import-Kompatibilität bestehen.
"""

from typing import Any, Dict, TypedDict

class Candle(TypedDict):
    t: Any
    o: float
    h: float
    low: float
    c: float
    v: float

class AgentResult(TypedDict, total=False):
    agent: str
    pair: str
    score: float
    confidence: float
    explanation: str
    inputs_fresh: bool
    latency_ms: int
    breakdown: Dict[str, Any]
