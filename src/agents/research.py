from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

class ResearchAgent(Agent):
    """
    Conservative long-horizon bias from OHLCV only.
    Uses EMA200 slope and recent drawdown to dampen overtrading.
    Score in [-1, 1], typically small magnitude. Deterministic. No I/O.
    """
    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()
        n = len(candles)
        if n < 220:
            return self._result(pair, 0.0, 0.3, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        ema200_series = ema(closes, 200)
        if not ema200_series or len(ema200_series) < 50:
            return self._result(pair, 0.0, 0.3, "ema200 unavailable", inputs_fresh, t0)

        ema_last = ema200_series[-1]
        ema_prev = ema200_series[-50]
        slope_pct = (ema_last - ema_prev) / ema_last if ema_last else 0.0

        recent_closes = closes[-250:] if n >= 250 else closes
        peak = max(recent_closes)
        last = recent_closes[-1]
        dd_pct = (peak - last) / peak if peak > 0 else 0.0  # 0..1

        raw = 1.5 * slope_pct - 0.8 * dd_pct   # slow trend minus drawdown
        score = _clamp(raw, -0.6, 0.6)         # conservative cap

        base_conf = 0.65
        conf = base_conf - min(0.35, dd_pct * 0.5)
        if not inputs_fresh:
            conf = max(0.05, conf - 0.15)

        expl = (
            f"ema200_slope%={slope_pct*100:.3f}, dd%={dd_pct*100:.2f}, "
            f"trend_bias={1.5*slope_pct:.3f}, dd_penalty={0.8*dd_pct:.3f}"
        )
        return self._result(pair, float(score), float(conf), expl, inputs_fresh, t0)

    def _result(self, pair: str, score: float, conf: float, expl: str, fresh: bool, t0: float) -> AgentResult:
        return {
            "pair": pair,
            "score": float(score),
            "confidence": float(conf),
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }
