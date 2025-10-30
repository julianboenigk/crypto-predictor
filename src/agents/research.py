from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
import time


@dataclass
class ResearchResult:
    score: float
    confidence: float
    info: Dict[str, Any]
    inputs_fresh: bool


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize any OHLCV dataframe to columns: ['t','o','h','l','c','v'] (numeric; t=int ms)."""
    df = df.copy()
    wanted = ["t", "o", "h", "l", "c", "v"]
    lower_cols = [str(c).strip().lower() for c in df.columns]
    mapping = {}
    for src, dst in [
        ("time", "t"), ("timestamp", "t"), ("open", "o"),
        ("high", "h"), ("low", "l"), ("close", "c"), ("volume", "v"),
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


class ResearchAgent:
    """
    Research-style meta signal (macro-ish, smooth/slow):
      - ema200 slope% (directional drift)
      - local drawdown% (risk pressure)
      - trend_bias = slope% / 70  (empirically scaled to ~[-0.03,+0.03])
      - dd_penalty = dd% * 0.008 (e.g., 5% dd -> 0.04 penalty)
      - score = trend_bias - dd_penalty (clipped to [-0.30,+0.30])

    Confidence:
      - 0.60 baseline if enough data (>= 210 bars), else 0.30
      - slightly reduced when series very choppy (higher std of returns)
    """

    def __init__(self, data_dir: str = "data", freshness_ms: int = 75 * 60 * 1000):
        self.name = "research"
        self.data_dir = data_dir
        self.freshness_ms = freshness_ms

    def _load_csv(self, pair: str, interval: str = "15m") -> pd.DataFrame:
        f = Path(self.data_dir) / f"{pair}_{interval}.csv"
        if not f.exists():
            raise FileNotFoundError(f"Missing {f}")
        df = pd.read_csv(f)
        return _normalize_df(df)

    @staticmethod
    def _ema(series: pd.Series, n: int) -> pd.Series:
        return series.ewm(span=n, adjust=False).mean()

    def evaluate(self, pair: str, interval: str = "15m") -> ResearchResult:
        df = self._load_csv(pair, interval)

        # Freshness check
        now_ms = int(time.time() * 1000)
        last_ts = int(df["t"].iloc[-1])
        is_fresh = (now_ms - last_ts) <= self.freshness_ms

        if len(df) < 210:
            # Not enough history for robust ema200
            return ResearchResult(
                score=0.0,
                confidence=0.30,
                info={"ema200_slope%": None, "dd%": None, "trend_bias": 0.0, "dd_penalty": 0.0},
                inputs_fresh=is_fresh,
            )

        close = df["c"].astype(float).reset_index(drop=True)
        ema200 = self._ema(close, 200)

        # Slope% over the last 10 bars (percent change of ema)
        lookback = 10
        prev = float(ema200.iloc[-lookback]) if len(ema200) > lookback else float(ema200.iloc[-2])
        cur = float(ema200.iloc[-1])
        slope_pct = ((cur - prev) / max(abs(prev), 1e-12)) * 100.0

        # Simple rolling drawdown % over last 200 bars (peak-to-last)
        window = min(200, len(close))
        recent = close.iloc[-window:]
        peak = float(np.max(recent))
        last = float(recent.iloc[-1])
        dd_pct = max(0.0, (peak - last) / max(peak, 1e-12) * 100.0)

        # Trend bias & penalty (calibrated to your previous logs)
        trend_bias = slope_pct / 70.0  # e.g., -0.77% -> -0.011
        dd_penalty = dd_pct * 0.008    # e.g., 4.66% -> 0.037

        # Score = trend bias - drawdown penalty (bounded)
        raw_score = float(trend_bias - dd_penalty)
        score = max(-0.30, min(0.30, raw_score))

        # Confidence: baseline on history, adjusted by realized choppiness
        ret = close.pct_change().dropna()
        vol = float(ret.std()) if len(ret) else 0.0
        base_conf = 0.60
        if len(df) < 400:
            base_conf -= 0.05
        if not is_fresh:
            base_conf -= 0.05
        # penalize high realized vol (softly)
        conf = max(0.30, min(0.85, base_conf - min(0.15, vol * 2.0)))

        info = {
            "ema200_slope%": round(slope_pct, 3),
            "dd%": round(dd_pct, 2),
            "trend_bias": round(trend_bias, 3),
            "dd_penalty": round(dd_penalty, 3),
        }

        return ResearchResult(
            score=score,
            confidence=conf,
            info=info,
            inputs_fresh=is_fresh,
        )
