from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any
from pathlib import Path

@dataclass
class TechnicalResult:
    score: float
    confidence: float
    info: Dict[str, Any]
    inputs_fresh: bool = True


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    # Same normalization idea as the client, duplicated locally to avoid import coupling
    df = df.copy()
    wanted = ["t", "o", "h", "l", "c", "v"]
    lower_cols = [str(c).strip().lower() for c in df.columns]
    mapping = {}
    for src, dst in [
        ("time", "t"), ("timestamp", "t"), ("open", "o"),
        ("high", "h"), ("low", "l"), ("close", "c"),
        ("volume", "v")
    ]:
        if src in lower_cols:
            mapping[df.columns[lower_cols.index(src)]] = dst
    if mapping:
        df = df.rename(columns=mapping)
    if all(col in df.columns for col in wanted):
        df = df[wanted]
    else:
        take = list(df.columns)[:6]
        df = df[take]
        df.columns = wanted

    for c in wanted:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["t", "c"]).reset_index(drop=True)
    df["t"] = df["t"].astype(int)
    df = df.sort_values("t").drop_duplicates(subset=["t"], keep="last").reset_index(drop=True)
    return df


class TechnicalAgent:
    """
    Technical analysis agent:
    - Computes EMA200, RSI14, ATR14
    - Scoring logic: trend + RSI-based momentum
    """

    def __init__(self):
        self.name = "technical"

    def _load_csv(self, pair: str, interval: str = "15m", data_dir: str = "data") -> pd.DataFrame:
        f = Path(data_dir) / f"{pair}_{interval}.csv"
        if not f.exists():
            raise FileNotFoundError(f"Missing {f}")
        df = pd.read_csv(f)
        df = _normalize_df(df)
        return df

    def _ema(self, series: pd.Series, n: int) -> pd.Series:
        return series.ewm(span=n, adjust=False).mean()

    def _rsi(self, series: pd.Series, n: int = 14) -> pd.Series:
        delta = series.diff()
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        avg_gain = pd.Series(gain).rolling(window=n).mean()
        avg_loss = pd.Series(loss).rolling(window=n).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        return 100 - (100 / (1 + rs))

    def _atr(self, df: pd.DataFrame, n: int = 14) -> pd.Series:
        tr = pd.concat([
            df["h"] - df["l"],
            (df["h"] - df["c"].shift()).abs(),
            (df["l"] - df["c"].shift()).abs()
        ], axis=1).max(axis=1)
        return tr.rolling(window=n).mean()

    def evaluate(self, pair: str, interval: str = "15m", data_dir: str = "data") -> TechnicalResult:
        df = self._load_csv(pair, interval, data_dir)

        if len(df) < 210:
            return TechnicalResult(score=0.0, confidence=0.2, info={"error": "not_enough_data"}, inputs_fresh=False)

        ema200 = self._ema(df["c"], 200)
        rsi14 = self._rsi(df["c"], 14)
        atr14 = self._atr(df, 14)

        price = float(df["c"].iloc[-1])
        ema_val = float(ema200.iloc[-1])
        rsi_val = float(rsi14.iloc[-1])
        atr_val = float(atr14.iloc[-1])
        atr_pct = float(atr_val / price * 100) if price > 0 else 0.0

        # Trend and RSI signals
        trend = "up" if price > ema_val else "down"
        rsi_sig = 0.0
        if rsi_val < 30:
            rsi_sig = +0.5
        elif rsi_val > 70:
            rsi_sig = -0.5

        base_score = 0.0
        base_score += +0.3 if trend == "up" else -0.3
        base_score += rsi_sig

        # Clamp
        score = max(-1.0, min(1.0, base_score))
        confidence = 0.6 + 0.1 * (1.0 - min(1.0, atr_pct / 5.0))  # less volatility → higher confidence

        info = {
            "price": round(price, 2),
            "ema200": round(ema_val, 2),
            "rsi14": round(rsi_val, 1),
            "atr_pct": round(atr_pct, 2),    # ✅ standardized key
            "trend": trend,
            "rsi_sig": round(rsi_sig, 2),
        }
        # backward compat field for existing logs
        info["atr%"] = info["atr_pct"]

        return TechnicalResult(score=score, confidence=confidence, info=info, inputs_fresh=True)
