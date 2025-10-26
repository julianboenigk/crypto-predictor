from __future__ import annotations
from typing import Protocol, Sequence, TypedDict

class Candle(TypedDict):
    t: int
    o: float
    h: float
    low: float
    c: float
    v: float

class AgentResult(TypedDict):
    pair: str
    score: float
    confidence: float
    explanation: str
    inputs_fresh: bool
    latency_ms: int

class Agent(Protocol):
    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult: ...
