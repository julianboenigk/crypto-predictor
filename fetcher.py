import time
from typing import Dict, List
import requests
import pandas as pd
import config

BINANCE = "https://api.binance.com"

def _get(path: str, params: dict) -> requests.Response:
    r = requests.get(f"{BINANCE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r

def _eurusdt() -> float:
    # how many USDT per 1 EUR
    r = _get("/api/v3/ticker/price", {"symbol": "EURUSDT"})
    return float(r.json()["price"])

def _klines(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    r = _get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    cols = ["t","o","h","l","c","v","ct","qv","n","tb","tqv","ig"]
    df = pd.DataFrame(r.json(), columns=cols)
    df = df[["t","o","h","l","c"]].astype({"o":"float64","h":"float64","l":"float64","c":"float64"})
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("Europe/Berlin")
    return df

def last_candle_fresh(df: pd.DataFrame) -> bool:
    if df.empty: return False
    if len(df) >= 2:
        period = (df["t"].iloc[-1] - df["t"].iloc[-2]).total_seconds()
    else:
        period = 300
    allowed = max(config.DATA_FRESHNESS_SEC, int(period * 2))
    ts = int(df.iloc[-1]["t"].tz_convert("UTC").timestamp())
    return (time.time() - ts) <= allowed

def get_markets(ids: List[str]) -> pd.DataFrame:
    eurusdt = _eurusdt()
    rows = []
    for cid in ids:
        sym = config.SYMBOL_MAP.get(cid)
        if not sym: continue
        try:
            r = _get("/api/v3/ticker/price", {"symbol": sym})
            usdt = float(r.json()["price"])
            eur = usdt / eurusdt if eurusdt > 0 else None
            rows.append({"id": cid, "symbol": sym, "current_price_eur": eur})
        except Exception:
            continue
    return pd.DataFrame(rows)

def get_ohlc(coin_id: str) -> pd.DataFrame:
    sym = config.SYMBOL_MAP.get(coin_id)
    if not sym:
        return pd.DataFrame(columns=["t","o","h","l","c"])
    return _klines(sym, config.BINANCE_INTERVAL, config.BINANCE_LIMIT)

def load_all_ohlc(ids: List[str]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for cid in ids:
        try:
            df = get_ohlc(cid)
            if not df.empty and len(df) >= config.EMA_LEN and last_candle_fresh(df):
                out[cid] = df
        except Exception:
            continue
    return out
