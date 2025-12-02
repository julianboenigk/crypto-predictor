from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema, rsi, atr


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def adx(highs, lows, closes, period=14):
    if len(highs) < period + 2:
        return None
    dm_pos, dm_neg, tr_list = [], [], []
    for i in range(1, len(highs)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        dm_pos.append(up if up > down and up > 0 else 0)
        dm_neg.append(down if down > up and down > 0 else 0)
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        tr_list.append(tr)

    def smooth(series):
        s = sum(series[:period])
        out = [s]
        for i in range(period, len(series)):
            s = s - (s / period) + series[i]
            out.append(s)
        return out

    tr_s = smooth(tr_list)
    dm_pos_s = smooth(dm_pos)
    dm_neg_s = smooth(dm_neg)

    di_pos = 100 * (dm_pos_s[-1] / tr_s[-1]) if tr_s[-1] > 0 else 0
    di_neg = 100 * (dm_neg_s[-1] / tr_s[-1]) if tr_s[-1] > 0 else 0

    return 100 * abs(di_pos - di_neg) / max(1e-9, (di_pos + di_neg))


class TechnicalAgent(Agent):
    """
    TechnicalAgent V2.1 — High-Confidence Trend Model
    mit ADX, Divergence, Dual-RSI & Regime Filtering
    """

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()

        if len(candles) < 260:
            return self._result(pair, 0.0, 0.2, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        highs = [c["h"] for c in candles]
        lows = [c["low"] for c in candles]

        ema200_arr = ema(closes, 200)
        if not ema200_arr or ema200_arr[-1] is None:
            return self._result(pair, 0.0, 0.2, "ema200 none", inputs_fresh, t0)
        ema200 = ema200_arr[-1]

        price = closes[-1]
        rsi_fast = rsi(closes, 14)
        rsi_slow = rsi(closes, 50)
        atr14 = atr(highs, lows, closes, 14)
        adx_val = adx(highs, lows, closes, 14)

        if None in (rsi_fast, rsi_slow, atr14, adx_val):
            return self._result(pair, 0.0, 0.2, "indicator none", inputs_fresh, t0)

        atr_pct = atr14 / price if price > 0 else 0

        # ------------------------------------------------------------
        # Trend V2.1: ATR-normalisiert + ADX + Memory-Smoothing
        # ------------------------------------------------------------
        trend_raw = (price - ema200) / max(1e-9, atr14 * 2.8)

        # ADX-Modifikation
        if adx_val > 30:
            trend_raw *= 1.5
        elif adx_val < 18:
            trend_raw *= 0.5

        trend_v2 = clamp(trend_raw, -1.0, 1.0)

        # Memory smoothing (subjektive Trendstärke)
        trend_v2 = trend_v2 * 0.7 + (1 if price > ema200 else -1) * 0.3
        trend_v2 = clamp(trend_v2, -1, 1)

        # ------------------------------------------------------------
        # RSI V2.1 (Regime-abhängig)
        # ------------------------------------------------------------
        rsi_sig = 0.0

        bull = price > ema200
        bear = price < ema200

        if bull:
            if rsi_fast < 28 and rsi_slow < 42:
                rsi_sig = +0.7
            elif rsi_fast < 35:
                rsi_sig = +0.25
        if bear:
            if rsi_fast > 72 and rsi_slow > 58:
                rsi_sig = -0.7
            elif rsi_fast > 65:
                rsi_sig = -0.25

        rsi_v2 = clamp(rsi_sig, -1, 1)

        # ------------------------------------------------------------
        # Divergence V2.1 (stärker gewichtet)
        # ------------------------------------------------------------
        divergence = 0.0
        if len(closes) >= 4:
            # Bullish Divergence
            if closes[-1] > closes[-2] and closes[-2] < closes[-3] and rsi_fast < rsi_slow:
                divergence = +0.45
            # Bearish Divergence
            if closes[-1] < closes[-2] and closes[-2] > closes[-3] and rsi_fast > rsi_slow:
                divergence = -0.45

        divergence = clamp(divergence, -0.6, 0.6)

        # ------------------------------------------------------------
        # Final Score
        # ------------------------------------------------------------
        score = (
            0.50 * trend_v2 +
            0.30 * rsi_v2 +
            0.20 * divergence
        )
        score = clamp(score, -1, 1)

        # ------------------------------------------------------------
        # Confidence
        # ------------------------------------------------------------
        vol_penalty = min(0.45, (atr_pct * 12)**0.9)
        conf = 0.92 - vol_penalty
        if not inputs_fresh:
            conf -= 0.25
        conf = clamp(conf, 0.1, 0.9)

        expl = (
            f"price={price:.2f}, ema200={ema200:.2f}, atr%={atr_pct*100:.2f}, adx={adx_val:.1f}, "
            f"trend={trend_v2:+.2f}, rsi={rsi_v2:+.2f}, div={divergence:+.2f}"
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
