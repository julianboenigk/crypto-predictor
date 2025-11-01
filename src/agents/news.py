# src/agents/news.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

NEWS_DIR = os.path.join("data", "news")
TTL_SEC = 90 * 60  # consider news fresh for 90 minutes

@dataclass
class NewsRecord:
    bias: float = 0.0      # [-1, +1]
    novelty: float = 0.5   # [0, 1]
    amp: float = 0.5       # [0, 1] amplitude/weight for effect sizing
    ts: int = 0            # unix seconds
    raw: Dict[str, Any] = None

def _parse_ts_any(ts_val: Any) -> int:
    """
    Accept int, float, or ISO-8601 string (e.g. '2025-11-01T14:04:09.642519+00:00').
    Return unix seconds (int). Fallback to 0 if parsing fails.
    """
    if ts_val is None:
        return 0
    if isinstance(ts_val, int):
        return ts_val
    if isinstance(ts_val, float):
        return int(ts_val)
    if isinstance(ts_val, str):
        s = ts_val.strip()
        # 'Z' suffix → normalize to +00:00
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # If it's a pure integer in a string
        if s.isdigit():
            try:
                return int(s)
            except Exception:
                pass
        try:
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp())
        except Exception:
            return 0
    return 0

def _load_news(pair: str) -> Optional[NewsRecord]:
    path = os.path.join(NEWS_DIR, f"{pair}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    # Be defensive with keys
    bias = float(data.get("bias", 0.0) or 0.0)          # [-1, 1]
    novelty = float(data.get("novelty", 0.5) or 0.5)    # [0, 1]
    amp = float(data.get("amp", 0.5) or 0.5)            # [0, 1]
    ts = _parse_ts_any(data.get("ts"))

    return NewsRecord(bias=bias, novelty=novelty, amp=amp, ts=ts, raw=data)

def _fresh(ts: int, ttl_sec: int = TTL_SEC) -> bool:
    if ts <= 0:
        return False
    return (int(time.time()) - ts) <= ttl_sec

def _score_from_components(bias: float, novelty: float, amp: float) -> float:
    """
    Compose a single news score.
    - bias drives direction ([-1, +1])
    - novelty modulates intensity (0..1 → map to [-1, +1] around 0.5)
    - amp scales overall impact (0..1)
    """
    nov_centered = (novelty - 0.5) * 2.0  # [-1, +1]
    base = 0.8 * bias + 0.2 * nov_centered
    score = base * max(0.0, min(1.0, amp))
    # clamp to [-1, 1]
    return max(-1.0, min(1.0, score))

class NewsAgent:
    """
    Public interface used by src/app/main.py:
      evaluate(pair: str) -> Dict[str, Any] with keys:
        score, conf, bias, novelty, amp, ts_fresh, ts
    """

    def __init__(self, ttl_sec: int = TTL_SEC) -> None:
        self.ttl_sec = ttl_sec

    def evaluate(self, pair: str) -> Dict[str, Any]:
        rec = _load_news(pair)
        if rec is None:
            # No data = neutral, modest confidence
            return {
                "score": 0.0,
                "conf": 0.35,   # matches previous prints
                "bias": 0.0,
                "novelty": 0.5,
                "amp": 0.5,
                "ts_fresh": False,
                "ts": 0,
            }

        ts_ok = _fresh(rec.ts, self.ttl_sec)
        score = _score_from_components(rec.bias, rec.novelty, rec.amp)

        # Confidence: keep baseline similar to historical logs, boost if fresh
        conf = 0.35 + (0.10 if ts_ok else 0.0)
        conf = float(max(0.0, min(1.0, conf)))

        return {
            "score": float(score),
            "conf": conf,
            "bias": float(rec.bias),
            "novelty": float(rec.novelty),
            "amp": float(rec.amp),
            "ts_fresh": bool(ts_ok),
            "ts": int(rec.ts) if rec.ts else 0,
        }

# convenience factory used by main
def make_agent(ttl_sec: int = TTL_SEC) -> NewsAgent:
    return NewsAgent(ttl_sec=ttl_sec)
