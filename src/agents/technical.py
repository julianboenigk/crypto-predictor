from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema, rsi, atr


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class TechnicalAgent(Agent):
    """
    TechnicalAgent V2 – Trend + Dual-RSI, ATR-normalisiert.
    """

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()

        if len(candles) < 260:
            return self._result(pair, 0.0, 0.2, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        highs  = [c["h"] for c in candles]
        lows   = [c["low"] for c in candles]

        ema200_arr = ema(closes, 200)
        if not ema200_arr or ema200_arr[-1] is None:
            return self._result(pair, 0.0, 0.2, "ema200 none", inputs_fresh, t0)
        ema200 = ema200_arr[-1]

        rsi_fast = rsi(closes, 14)
        rsi_slow = rsi(closes, 50)
        atr14 = atr(highs, lows, closes, 14)

        if None in (rsi_fast, rsi_slow, atr14):
            return self._result(pair, 0.0, 0.2, "indicator None", inputs_fresh, t0)

        price = closes[-1]
        if price <= 0 or atr14 <= 0:
            return self._result(pair, 0.0, 0.2, "invalid price/atr", inputs_fresh, t0)

        atr_pct = atr14 / price

        # 1) Trend über ATR-normalisierte Distanz
        K = 2.0
        trend_raw = (price - ema200) / max(1e-9, (atr14 * K))
        trend = clamp(trend_raw * 0.8, -1.0, +1.0)  # leichte Glättung

        # 2) Dual-RSI Signale
        rsi_sig = 0.0
        if rsi_fast < 30 and rsi_slow < 45:
            rsi_sig = +0.5
        elif rsi_fast > 70 and rsi_slow > 55:
            rsi_sig = -0.5
        elif rsi_fast < 35:
            rsi_sig = +0.2
        elif rsi_fast > 65:
            rsi_sig = -0.2

        rsi_sig = clamp(rsi_sig, -1.0, +1.0)

        # 3) Score
        score = 0.7 * trend + 0.3 * rsi_sig
        score = clamp(score, -1.0, 1.0)

        # 4) Confidence
        conf = 0.8
        conf -= min(0.4, atr_pct * 10.0)
        if not inputs_fresh:
            conf -= 0.2
        conf = clamp(conf, 0.1, 0.9)

        expl = (
            f"price={price:.2f}, ema200={ema200:.2f}, atr%={atr_pct*100:.2f}, "
            f"trend_raw={trend_raw:.2f}, trend={trend:.2f}, "
            f"rsi_fast={rsi_fast:.1f}, rsi_slow={rsi_slow:.1f}, rsi_sig={rsi_sig:+.2f}"
        )

        return self._result(pair, float(score), float(conf), expl, inputs_fresh, t0)

    def _result(self, pair: str, score: float, conf: float, expl: str, fresh: bool, t0: float) -> AgentResult:
        return {
            "pair": pair,
            "score": score,
            "confidence": conf,
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }