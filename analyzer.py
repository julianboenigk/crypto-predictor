import numpy as np
import pandas as pd
from typing import Dict, List
import config

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int) -> pd.Series:
    delta = series.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    roll_down = pd.Series(down, index=series.index).ewm(alpha=1/length, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-12)
    return 100 - (100/(1+rs))

def tr(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    hl = high - low
    hc = (high - prev_close).abs()
    lc = (low - prev_close).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1)

def atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    return tr(high, low, close).ewm(alpha=1/length, adjust=False).mean()

def evaluate_coin(coin_id: str, ohlc: pd.DataFrame) -> Dict:
    df = ohlc.copy()
    df["ema200"] = ema(df["c"], config.EMA_LEN)
    df["rsi14"] = rsi(df["c"], config.RSI_LEN)
    df["atr14"] = atr(df["h"], df["l"], df["c"], config.ATR_LEN)

    if df["ema200"].isna().sum() > 0 or len(df) < config.EMA_LEN + 5:
        return {}

    row = df.iloc[-1]
    price = float(row["c"])
    ema200 = float(row["ema200"])
    rsi14 = float(row["rsi14"])
    atr14 = float(row["atr14"])

    signal = None
    stop = None
    target = None
    rr = None
    exp_ret = None

    if price > ema200 and rsi14 > 50:
        stop = price - 1.5 * atr14
        target = price + config.MIN_RR * (price - stop)
        rr = (target - price) / (price - stop) if (price - stop) > 0 else None
        exp_ret = (target/price - 1) * 100
        if rr and rr >= config.MIN_RR and exp_ret >= config.MIN_EXPECTED_RETURN_PCT:
            signal = "LONG"

    if signal is None and price < ema200 and rsi14 < 50:
        stop = price + 1.5 * atr14
        target = price - config.MIN_RR * (stop - price)
        rr = (price - target) / (stop - price) if (stop - price) > 0 else None
        exp_ret = (1 - target/price) * 100
        if rr and rr >= config.MIN_RR and exp_ret >= config.MIN_EXPECTED_RETURN_PCT:
            signal = "SHORT"

    if signal is None:
        return {}

    return {
        "coin_id": coin_id,
        "price": round(price, 6),
        "ema200": round(ema200, 6),
        "rsi14": round(rsi14, 2),
        "atr14": round(atr14, 6),
        "signal": signal,
        "stop": round(stop, 6),
        "target": round(target, 6),
        "rr": round(rr, 2),
        "expected_return_pct": round(exp_ret, 2),
        "timestamp": str(df.iloc[-1]["t"])
    }

def scan_all(ohlc_map: Dict[str, pd.DataFrame]) -> List[Dict]:
    out = []
    for cid, df in ohlc_map.items():
        res = evaluate_coin(cid, df)
        if res:
            out.append(res)
    return out
