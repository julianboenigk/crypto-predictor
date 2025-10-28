from __future__ import annotations
from typing import List, Optional, Tuple
import time, os
import requests
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

_BASE = "https://api.binance.com"
_INTERVALS = {"1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"}

_API_KEY = os.getenv("BINANCE_API_KEY")  # optional header

def get_ohlcv(
    pair: str, interval: str, limit: int = 500, end_ms: Optional[int] = None
) -> Tuple[List[List[float | int]], int]:
    if interval not in _INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")

    params: list[tuple[str, str]] = [
        ("symbol", pair),
        ("interval", interval),
        ("limit", str(min(limit, 1000))),
    ]
    if end_ms is not None:
        params.append(("endTime", str(end_ms)))

    headers = {"X-MBX-APIKEY": _API_KEY} if _API_KEY else None
    r = requests.get(f"{_BASE}/api/v3/klines", params=params, headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    rows: List[List[float | int]] = []
    for k in data:
        rows.append([int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[6])])
    server_time = int(time.time() * 1000)
    return rows, server_time
