import os, time, math
from typing import Dict, List
import requests
import pandas as pd
from dateutil import tz
from datetime import datetime
import config

BASE = "https://api.coingecko.com/api/v3"

def _headers():
    h = {"accept": "application/json"}
    if config.COINGECKO_API_KEY:
        h["x-cg-pro-api-key"] = config.COINGECKO_API_KEY
    return h

def now_ms() -> int:
    return int(time.time() * 1000)

def get_markets(ids: List[str]) -> pd.DataFrame:
    out = []
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        r = requests.get(
            f"{BASE}/coins/markets",
            params={
                "vs_currency": config.VS_CURRENCY,
                "ids": ",".join(batch),
                "order": "market_cap_desc",
                "per_page": len(batch),
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "1h,24h"
            },
            headers=_headers(), timeout=30
        )
        r.raise_for_status()
        out += r.json()
    return pd.DataFrame(out)

def get_ohlc(coin_id: str, days: int = 1) -> pd.DataFrame:
    r = requests.get(
        f"{BASE}/coins/{coin_id}/ohlc",
        params={"vs_currency": config.VS_CURRENCY, "days": days},
        headers=_headers(), timeout=30
    )
    r.raise_for_status()
    data = r.json()
    if not data:
        return pd.DataFrame(columns=["t","o","h","l","c"])
    df = pd.DataFrame(data, columns=["t","o","h","l","c"])
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("Europe/Berlin")
    return df

def last_candle_fresh(df: pd.DataFrame) -> bool:
    if df.empty:
        return False
    if len(df) >= 2:
        period = (df["t"].iloc[-1] - df["t"].iloc[-2]).total_seconds()
    else:
        period = 300
    allowed = max(config.DATA_FRESHNESS_SEC, int(period * 2))
    ts = int(df.iloc[-1]["t"].tz_convert("UTC").timestamp())
    return (time.time() - ts) <= allowed

def load_all_ohlc(ids: List[str]) -> Dict[str, pd.DataFrame]:
    out = {}
    for cid in ids:
        try:
            o = get_ohlc(cid, days=1)
            if last_candle_fresh(o):
                out[cid] = o
        except Exception:
            continue
    return out
