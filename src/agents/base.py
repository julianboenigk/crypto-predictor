# src/agents/base.py

"""
Legacy placeholder – Technical Agent nutzt keine gemeinsame Base mehr.
AI Agents nutzen die neue AIAgent Base (see src/agents/ai_base.py).
Kein echter Code notwendig. Datei bleibt für Import-Kompatibilität bestehen.
"""

from typing import TypedDict, Any

class Candle(TypedDict):
    t: Any
    o: float
    h: float
    l: float
    c: float
    v: float

class AgentResult(TypedDict):
    agent: str
    score: float
    confidence: float
