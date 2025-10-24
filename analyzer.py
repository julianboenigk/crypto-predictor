# analyzer.py
import math
from typing import Dict, List
import pandas as pd
import numpy as np
import config

# ---- Tunables --------------------------------------------------------------
STOP_ATR_MULT = 1.2                 # tighter stops → nearer targets
HIGH_RSI_LONG = 57.0                # stronger momentum gate
LOW_RSI_SHORT = 43.0
VOLA_MIN_PCT = 0.8                  # skip dead pairs: ATR/Price < 0.8%
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False, min_periods=n).mean()

def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    ma_up = up.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    ma_down = down.ewm(alpha=1/n, adjust=False, min_periods=n).mean()
    rs = ma_up / ma_down.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["c"].shift(1)
    tr = pd.concat([
        df["h"] - df["l"],
        (df["h"] - prev_close).abs(),
        (df["l"] - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def _fresh_enough(last_ts: pd.Timestamp) -> bool:
    now = pd.Timestamp.utcnow().tz_localize(None)
    return (now - last_ts).total_seconds() <= config.DATA_FRESHNESS_SEC

def _build_signal(side: str, coin_id: str, price: float, atr: float,
                  ema200: float, rsi14: float) -> dict | None:
    if atr <= 0 or price <= 0:
        return None

    if side == "LONG":
        stop = price - STOP_ATR_MULT * atr
        risk = price - stop
        target_by_rr  = price + config.MIN_RR * risk
        target_by_ret = price * (1 + config.MIN_EXPECTED_RETURN_PCT / 100.0)
        target = max(target_by_rr, target_by_ret)
        expected_return_pct = (target / price - 1.0) * 100.0
        rr = (target - price) / max(risk, 1e-12)
    else:
        stop = price + STOP_ATR_MULT * atr
        risk = stop - price
        target_by_rr  = price - config.MIN_RR * risk
        target_by_ret = price * (1 - config.MIN_EXPECTED_RETURN_PCT / 100.0)
        target = min(target_by_rr, target_by_ret)
        expected_return_pct = (1.0 - target / price) * 100.0
        rr = (price - target) / max(risk, 1e-12)

    if rr < config.MIN_RR:
        return None
    if expected_return_pct < config.MIN_EXPECTED_RETURN_PCT:
        return None

    return {
        "timestamp": None,  # set later
        "coin_id": coin_id,
        "signal": side,
        "price": float(round(price, 8)),
        "stop": float(round(stop, 8)),
        "target": float(round(target, 8)),
        "rr": float(round(rr, 3)),
        "expected_return_pct": float(round(expected_return_pct, 3)),
        "ema200": float(round(ema200, 8)),
        "rsi14": float(round(rsi14, 2)),
        "atr14": float(round(atr, 8)),
    }

def scan_one(coin_id: str, df: pd.DataFrame) -> List[dict]:
    """
    df columns: t,o,h,l,c (t is naive UTC)
    """
    out: List[dict] = []
    if df is None or df.empty or len(df) < max(config.EMA_LEN, config.RSI_LEN, config.ATR_LEN) + 5:
        return out

    close = df["c"].astype(float)
    ema200 = _ema(close, config.EMA_LEN)
    rsi14 = _rsi(close, config.RSI_LEN)
    atr14 = _atr(df, config.ATR_LEN)

    last = df.iloc[-1]
    last_ts = pd.to_datetime(last["t"])
    if not _fresh_enough(last_ts):
        return out

    p = float(last["c"])
    e = float(ema200.iloc[-1])
    r = float(rsi14.iloc[-1])
    a = float(atr14.iloc[-1])

    # volatility filter
    vola_pct = (a / max(p, 1e-12)) * 100.0
    if vola_pct < VOLA_MIN_PCT:
        return out

    # LONG gate
    if p > e and r >= HIGH_RSI_LONG:
        sig = _build_signal("LONG", coin_id, p, a, e, r)
        if sig:
            sig["timestamp"] = last_ts.isoformat() + "Z"
            out.append(sig)

    # SHORT gate
    if p < e and r <= LOW_RSI_SHORT:
        sig = _build_signal("SHORT", coin_id, p, a, e, r)
        if sig:
            sig["timestamp"] = last_ts.isoformat() + "Z"
            out.append(sig)

    return out

def scan_all(ohlc_map: Dict[str, pd.DataFrame]) -> List[dict]:
    signals: List[dict] = []
    for key, df in ohlc_map.items():
        try:
            signals.extend(scan_one(key, df))
        except Exception:
            continue
    return signals
