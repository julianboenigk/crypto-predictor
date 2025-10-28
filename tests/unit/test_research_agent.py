from __future__ import annotations

from typing import List, TypedDict
from src.agents.research import ResearchAgent


class C(TypedDict):
    t: int
    o: float
    h: float
    low: float
    c: float
    v: float


def _mk_candles(n: int, start: float, step: float) -> List[C]:
    out: List[C] = []
    ts = 1_700_000_000_000
    px = start
    for i in range(n):
        open_px = px
        high_px = px * 1.01
        low_px = px * 0.99
        close_px = px + step
        vol = 10.0
        out.append(
            {"t": ts + i * 60_000, "o": open_px, "h": high_px, "low": low_px, "c": close_px, "v": vol}
        )
        px = close_px
    return out


def test_research_positive_trend_bias():
    candles = _mk_candles(260, 100.0, 0.2)  # gentle uptrend
    res = ResearchAgent().run("BTCUSDT", candles, True)
    assert res["confidence"] >= 0.3
    assert res["score"] > 0.0


def test_research_handles_short_series():
    candles = _mk_candles(100, 100.0, 0.0)
    res = ResearchAgent().run("BTCUSDT", candles, True)
    assert res["confidence"] <= 0.3
    assert -0.6 <= res["score"] <= 0.6
