from __future__ import annotations
import time
from typing import List, Tuple, Optional
import requests

_BASE = "https://api.binance.com"

_INTERVALS = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"}

def get_ohlcv(pair: str, interval: str, limit: int = 500, end_ms: Optional[int] = None
             ) -> Tuple[List[List[float]], int]:
    """
    Returns:
      (rows, server_time_ms)
      rows = [[open_time_ms, open, high, low, close, volume, close_time_ms], ...]
    """
    if interval not in _INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    params = {"symbol": pair, "interval": interval, "limit": min(limit, 1000)}
    if end_ms:
        params["endTime"] = end_ms
    r = requests.get(f"{_BASE}/api/v3/klines", params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    rows = []
    for k in data:
        rows.append([k[0], float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), k[6]])
    server_time = int(time.time() * 1000)
    return rows, server_time
