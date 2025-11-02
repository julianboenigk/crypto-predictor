from __future__ import annotations
import os, time, json, requests
from typing import Any, Dict, List, Union

_BINANCE_BASE = os.getenv("BINANCE_BASE", "https://api.binance.com")
_TIMEOUT = float(os.getenv("BINANCE_TIMEOUT_SEC", "10"))
_MAX_RETRIES = int(os.getenv("BINANCE_MAX_RETRIES", "2"))

_VALID_INTERVALS = {
    "1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d","3d","1w","1M"
}

def _sleep_backoff(attempt: int) -> None:
    time.sleep(min(1.0 * (2 ** attempt), 5.0))

def _req(path: str, params: Dict[str, Any]) -> requests.Response:
    url = f"{_BINANCE_BASE}{path}"
    headers = {"User-Agent": "crypto-predictor/0.1"}
    for attempt in range(_MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)
            if r.status_code in (429, 418) or r.status_code >= 500:
                _sleep_backoff(attempt)
                continue
            return r
        except requests.RequestException:
            _sleep_backoff(attempt)
    return requests.get(url, params=params, headers=headers, timeout=_TIMEOUT)

def _validate_interval(interval: str) -> str:
    iv = interval.strip()
    if iv not in _VALID_INTERVALS:
        raise ValueError(f"invalid interval '{interval}'. allowed: {sorted(_VALID_INTERVALS)}")
    return iv

def get_ohlcv(
    pair: str,
    interval: str,
    limit: int = 300,
    as_dataframe: bool = False,
) -> Union[List[List[Any]], "pandas.DataFrame", None]:
    """
    Fetch klines from Binance Spot API.
    Each kline: [open_time, open, high, low, close, volume,
                 close_time, quote_asset_volume, trades,
                 taker_buy_base_vol, taker_buy_quote_vol, ignore]
    """
    iv = _validate_interval(interval)
    lim = max(1, min(int(limit), 1000))
    params = {"symbol": pair.upper(), "interval": iv, "limit": lim}
    r = _req("/api/v3/klines", params)
    if r.status_code != 200:
        print(f"[WARN] klines {pair} {iv} HTTP {r.status_code}")
        return None
    try:
        data = r.json()
    except json.JSONDecodeError:
        print(f"[WARN] invalid JSON for {pair}")
        return None
    if not isinstance(data, list) or not data:
        return None

    if as_dataframe:
        import pandas as pd
        cols = [
            "open_time","open","high","low","close","volume",
            "close_time","quote_asset_volume","trades",
            "taker_buy_base_vol","taker_buy_quote_vol","ignore"
        ]
        df = pd.DataFrame(data, columns=cols)
        for c in ["open","high","low","close","volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        df.set_index("close_time", inplace=True)
        return df
    return data

__all__ = ["get_ohlcv"]
