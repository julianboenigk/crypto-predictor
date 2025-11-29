from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema, rsi, atr


class TechnicalAgent(Agent):
    """
    Trenddominanter Technical-Agent:
    - Trend = smooth (price–EMA200 relation), nicht binär
    - RSI = leichte Modulation, kein Haupttreiber
    - Score = 85% Trend + 15% RSI
    """

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()

        # Datenumfang prüfen
        if len(candles) < 210:
            return self._result(pair, 0.0, 0.2, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        highs  = [c["h"] for c in candles]
        lows   = [c["low"] for c in candles]

        # Indikatoren
        ema200_list = ema(closes, 200)
        ema200 = ema200_list[-1] if ema200_list else None
        rsi14 = rsi(closes, 14)
        atr14 = atr(highs, lows, closes, 14)

        if ema200 is None or rsi14 is None or atr14 is None:
            return self._result(pair, 0.0, 0.2, "indicator None", inputs_fresh, t0)

        price = closes[-1]
        atr_pct = atr14 / price if price > 0 else 0.0

        # ----------------------------------------------------------------------
        # TREND (SMOOTH)
        # ----------------------------------------------------------------------
        # Verhältnis zwischen Preis und EMA200:
        # 1% Abstand → trend_raw ≈ 0.01
        trend_raw = (price - ema200) / ema200

        # Verstärkung: 5% Abstand → trend ≈ ±1.0
        trend = max(-1.0, min(1.0, trend_raw * 20))

        # ----------------------------------------------------------------------
        # RSI (leichte Modulation)
        # ----------------------------------------------------------------------
        rsi_sig = 0.0
        if rsi14 < 30:
            rsi_sig = +0.3
        elif rsi14 < 40:
            rsi_sig = +0.1
        elif rsi14 > 70:
            rsi_sig = -0.3
        elif rsi14 > 60:
            rsi_sig = -0.1

        # ----------------------------------------------------------------------
        # SCORE: trend-dominiert, rsi als leichte Gewichtung
        # ----------------------------------------------------------------------
        score = 0.85 * trend + 0.15 * rsi_sig
        score = max(-1.0, min(1.0, score))

        # ----------------------------------------------------------------------
        # CONFIDENCE: unverändert
        # ----------------------------------------------------------------------
        base_conf = 0.7
        vol_penalty = max(0.0, min(0.5, atr_pct * 10))  # ~0–0.5 bei 0–5% ATR
        fresh_penalty = 0.2 if not inputs_fresh else 0.0
        confidence = max(0.05, base_conf - vol_penalty - fresh_penalty)

        expl = (
            f"price={price:.2f}, ema200={ema200:.2f}, rsi14={rsi14:.1f}, "
            f"atr%={atr_pct*100:.2f}, trend_raw={trend_raw:+.4f}, "
            f"trend={trend:+.2f}, rsi_sig={rsi_sig:+.2f}"
        )

        return self._result(pair, score, confidence, expl, inputs_fresh, t0)

    def _result(
        self,
        pair: str,
        score: float,
        conf: float,
        expl: str,
        fresh: bool,
        t0: float
    ) -> AgentResult:
        return {
            "pair": pair,
            "score": float(score),
            "confidence": float(conf),
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }
