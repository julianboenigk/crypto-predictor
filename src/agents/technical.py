from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema, rsi, atr


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class TechnicalAgent(Agent):
    """
    Verbesserter Technical Agent:
    - Trendfilter: (price - ema200) / (ATR * K)
    - Dual-RSI: RSI14 + RSI50 zur Noise-Unterdrückung
    - Score = 0.7 * trend + 0.3 * rsi_sig
    - Confidence abhängig von ATR-Volatilität und Inputs-Frische
    """

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()

        if len(candles) < 260:  # 200 EMA + 50 RSI + Puffer
            return self._result(pair, 0.0, 0.2, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        highs  = [c["h"] for c in candles]
        lows   = [c["low"] for c in candles]

        # Core indicators
        ema200_list = ema(closes, 200)
        ema200 = ema200_list[-1] if ema200_list else None

        rsi_fast = rsi(closes, 14)
        rsi_slow = rsi(closes, 50)

        atr14 = atr(highs, lows, closes, 14)

        if ema200 is None or rsi_fast is None or rsi_slow is None or atr14 is None:
            return self._result(pair, 0.0, 0.2, "indicator None", inputs_fresh, t0)

        price = closes[-1]
        atr_pct = atr14 / price if price > 0 else 0.0

        # ----------------------------------------------------
        # 1) Trend über ATR-normalisierte Distanz
        # ----------------------------------------------------
        # (price - ema200) relativ zur Volatilität
        K = 2.0
        trend_raw = (price - ema200) / max(1e-9, (atr14 * K))
        trend = clamp(trend_raw, -1.0, +1.0)

        # ----------------------------------------------------
        # 2) Dual-RSI Signale (Noise-Free)
        # ----------------------------------------------------
        rsi_sig = 0.0

        # Extrembereiche nur wenn beide RSIs aligned
        if rsi_fast < 30 and rsi_slow < 45:
            rsi_sig = +0.5
        elif rsi_fast > 70 and rsi_slow > 55:
            rsi_sig = -0.5

        # Leichte Signale (nur fast nötig)
        elif rsi_fast < 35:
            rsi_sig = +0.2
        elif rsi_fast > 65:
            rsi_sig = -0.2

        # clamp
        rsi_sig = clamp(rsi_sig, -1.0, +1.0)

        # ----------------------------------------------------
        # 3) Score kombinieren
        # ----------------------------------------------------
        score = 0.7 * trend + 0.3 * rsi_sig
        score = clamp(score, -1.0, 1.0)

        # ----------------------------------------------------
        # 4) Confidence
        # ----------------------------------------------------
        conf = 0.8
        conf -= min(0.4, atr_pct * 10)  # Vol-Penalty
        if not inputs_fresh:
            conf -= 0.2                 # stale penalty
        conf = clamp(conf, 0.1, 0.9)

        # ----------------------------------------------------
        # 5) Erklärung
        # ----------------------------------------------------
        expl = (
            f"price={price:.2f}, ema200={ema200:.2f}, atr%={atr_pct*100:.2f}, "
            f"trend_raw={trend_raw:.2f}, trend={trend:.2f}, "
            f"rsi_fast={rsi_fast:.1f}, rsi_slow={rsi_slow:.1f}, rsi_sig={rsi_sig:+.2f}"
        )

        return self._result(pair, float(score), float(conf), expl, inputs_fresh, t0)

    # Standard-Adapter
    def _result(self, pair: str, score: float, conf: float, expl: str, fresh: bool, t0: float) -> AgentResult:
        return {
            "pair": pair,
            "score": score,
            "confidence": conf,
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }
