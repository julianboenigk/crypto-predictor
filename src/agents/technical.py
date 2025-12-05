from __future__ import annotations
import time
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult
from src.core.indicators import ema, rsi, atr


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class TechnicalAgent(Agent):
    """
    TechnicalAgent V2.2 – Trend + Dual-RSI, ATR-normalisiert.

    Ziele:
    - Trend ist klar dominanter Treiber (Gewicht 0.8).
    - Dual-RSI wirkt unterstützend (Gewicht 0.2).
    - ATR-normalisierte Distanz zu EMA200 als Kern-Edge.
    - Rauschen wird in einem zentralen Korridor hart gedämpft (Score-Deadzone).
    """

    EMA_LEN = 200
    RSI_FAST_LEN = 14
    RSI_SLOW_LEN = 50
    ATR_LEN = 14

    # ATR-Multiplikator für Trendnormalisierung (aggressiver als V2)
    TREND_K = 1.5

    # Deadzones
    TREND_DEADZONE = 0.25   # |trend_norm| < 0.25 -> abgeschwächt
    SCORE_DEADZONE = 0.15   # |score| < 0.15 -> auf 0 gesetzt

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()

        min_len = max(self.EMA_LEN, self.RSI_SLOW_LEN, self.ATR_LEN) + 10
        if len(candles) < min_len:
            return self._result(pair, 0.0, 0.2, "insufficient candles", inputs_fresh, t0)

        closes = [c["c"] for c in candles]
        highs  = [c["h"] for c in candles]
        lows   = [c["low"] for c in candles]

        # --- EMA200 ---
        ema_arr = ema(closes, self.EMA_LEN)
        if not ema_arr or ema_arr[-1] is None:
            return self._result(pair, 0.0, 0.2, "ema200 none", inputs_fresh, t0)
        ema200 = float(ema_arr[-1])

        # --- Indikatoren ---
        rsi_fast = rsi(closes, self.RSI_FAST_LEN)
        rsi_slow = rsi(closes, self.RSI_SLOW_LEN)
        atr14 = atr(highs, lows, closes, self.ATR_LEN)

        if None in (rsi_fast, rsi_slow, atr14):
            return self._result(pair, 0.0, 0.2, "indicator None", inputs_fresh, t0)

        price = float(closes[-1])
        atr14 = float(atr14)

        if price <= 0 or atr14 <= 0:
            return self._result(pair, 0.0, 0.2, "invalid price/atr", inputs_fresh, t0)

        atr_pct = atr14 / price  # relative Volatilität

        # ------------------------------------------------------------------
        # 1) ATR-normalisierter Trend (Price vs EMA200)
        # ------------------------------------------------------------------
        # Rohdistanz in ATR-Einheiten
        trend_raw = (price - ema200) / max(1e-9, (atr14 * self.TREND_K))
        # Grob auf [-3, 3] begrenzen, dann nach [-1, 1] skalieren
        trend_norm = clamp(trend_raw, -3.0, 3.0) / 3.0

        # Deadzone: kleine Abweichungen um 0 werden stark gedämpft
        if abs(trend_norm) < self.TREND_DEADZONE:
            trend_effective = trend_norm * 0.2
        else:
            # leichte Sättigung, um Extremwerte zu begrenzen
            trend_effective = clamp(trend_norm, -1.0, 1.0)

        # ------------------------------------------------------------------
        # 2) Dual-RSI Signale (Verschärfte Bereiche)
        # ------------------------------------------------------------------
        rsi_fast_f = float(rsi_fast)
        rsi_slow_f = float(rsi_slow)

        rsi_sig = 0.0

        # Stark bullisch
        if rsi_fast_f < 28 and rsi_slow_f < 45:
            rsi_sig = +0.7
        # Mild bullisch
        elif rsi_fast_f < 35 and rsi_slow_f < 50:
            rsi_sig = +0.3
        # Stark bearisch
        elif rsi_fast_f > 72 and rsi_slow_f > 55:
            rsi_sig = -0.7
        # Mild bearisch
        elif rsi_fast_f > 65 and rsi_slow_f > 50:
            rsi_sig = -0.3

        rsi_sig = clamp(rsi_sig, -1.0, 1.0)

        # ------------------------------------------------------------------
        # 3) Volatilitätslogik
        # ------------------------------------------------------------------
        # Extrem niedrige Volatilität: Trend ist oft Rauschen → Score dämpfen
        vol_regime = "normal"
        if atr_pct < 0.002:      # < 0.2%
            vol_regime = "ultra_low"
        elif atr_pct < 0.008:    # 0.2–0.8%
            vol_regime = "low"
        elif atr_pct > 0.06:     # > 6%
            vol_regime = "high"

        # Basis-Gewichte
        w_trend = 0.8
        w_rsi = 0.2

        if vol_regime == "ultra_low":
            # Sehr wenig Bewegung: fast alles ausblenden
            w_trend *= 0.4
            w_rsi *= 0.4
        elif vol_regime == "low":
            # Etwas vorsichtiger, aber noch handelbar
            w_trend *= 0.8
            w_rsi *= 0.8
        elif vol_regime == "high":
            # In sehr hoher Volatilität RSI leicht runternehmen
            w_rsi *= 0.7

        # ------------------------------------------------------------------
        # 4) Score-Berechnung mit Deadzone
        # ------------------------------------------------------------------
        score = w_trend * trend_effective + w_rsi * rsi_sig
        score = clamp(score, -1.0, 1.0)

        # zentrale Score-Deadzone: kleine Werte → neutral behandeln
        if abs(score) < self.SCORE_DEADZONE:
            score = 0.0

        # ------------------------------------------------------------------
        # 5) Confidence-Logik
        # ------------------------------------------------------------------
        conf = 0.9

        # Volatilitätsabhängig
        if vol_regime == "ultra_low":
            conf -= 0.4
        elif vol_regime == "low":
            conf -= 0.15
        elif vol_regime == "high":
            conf -= 0.25

        # Eingabefrischeit
        if not inputs_fresh:
            conf -= 0.15

        conf = clamp(conf, 0.1, 0.95)

        expl = (
            f"price={price:.4f}, ema200={ema200:.4f}, atr%={atr_pct*100:.2f}, "
            f"trend_raw={trend_raw:.2f}, trend_norm={trend_norm:.2f}, "
            f"trend_eff={trend_effective:.2f}, "
            f"rsi_fast={rsi_fast_f:.1f}, rsi_slow={rsi_slow_f:.1f}, rsi_sig={rsi_sig:+.2f}, "
            f"vol_regime={vol_regime}, w_trend={w_trend:.2f}, w_rsi={w_rsi:.2f}"
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