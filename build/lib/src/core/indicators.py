from __future__ import annotations
from typing import Sequence, List


def ema(prices: Sequence[float], period: int) -> List[float]:
    if period <= 0 or len(prices) < period:
        return []
    k = 2 / (period + 1)
    out: List[float] = []
    sma = sum(prices[:period]) / period
    out.append(sma)
    ema_prev = sma
    for p in prices[period:]:
        ema_prev = p * k + ema_prev * (1 - k)
        out.append(ema_prev)
    return out


def rsi(prices: Sequence[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> float | None:
    n = len(closes)
    if n < period + 1 or n != len(highs) or n != len(lows):
        return None
    trs: list[float] = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period
