# src/agents/sentiment.py
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

SENTIMENT_DIR = os.path.join("data", "sentiment")
TTL_SEC = 2 * 60 * 60  # consider sentiment fresh for 2h

@dataclass
class SentimentRecord:
    pol: float = 0.0      # polarity [-1, +1]
    vz: float = 0.0       # velocity/trend proxy [0..1], optional
    sig: float = 0.5      # signal confidence [0..1]
    ts: int = 0           # unix seconds
    raw: Dict[str, Any] = None

def _parse_ts_any(ts_val: Any) -> int:
    """
    Accept int, float, or ISO-8601 string (e.g. '2025-11-01T14:04:21.210365+00:00').
    Return unix seconds (int). Fallback to 0 if parsing fails.
    """
    if ts_val is None:
        return 0
    # Already an int
    if isinstance(ts_val, int):
        return ts_val
    # Floats
    if isinstance(ts_val, float):
        return int(ts_val)
    # Strings: try int first, then ISO-8601
    if isinstance(ts_val, str):
        s = ts_val.strip()
        # pure integer in string
        if s.isdigit():
            try:
                return int(s)
            except Exception:
                pass
        # ISO-8601 attempt
        try:
            # Handle 'Z' suffix, though your string shows '+00:00'
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp())
        except Exception:
            return 0
    return 0

def _load_sentiment(pair: str) -> Optional[SentimentRecord]:
    path = os.path.join(SENTIMENT_DIR, f"{pair}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    # Be defensive on keys; tolerate different casings/aliases
    pol = float(data.get("pol", data.get("polarity", 0.0)) or 0.0)
    vz  = float(data.get("vz", data.get("velocity", 0.0)) or 0.0)
    sig = float(data.get("sig", data.get("signal", 0.5)) or 0.5)
    ts  = _parse_ts_any(data.get("ts", data.get("timestamp")))

    return SentimentRecord(pol=pol, vz=vz, sig=sig, ts=ts, raw=data)

def _fresh(ts: int, ttl_sec: int = TTL_SEC) -> bool:
    if ts <= 0:
        return False
    return (int(time.time()) - ts) <= ttl_sec

def _score_from_components(pol: float, vz: float, sig: float) -> float:
    """
    Compose a single sentiment score.
    Keep it simple & consistent with prior logic:
      - polarity drives direction
      - velocity is currently neutral (0..1 with 0.5 meaning neutral). If your vz is already centered at 0.0, leave as-is.
      - sig gates the confidence (0..1)
    """
    # If your vz is centered at 0.0, this is fine. If it’s centered at 0.5, subtract 0.5 to make it symmetric.
    vz_centered = vz  # change to (vz - 0.5) * 2.0 if needed
    base = 0.8 * pol + 0.2 * vz_centered
    return float(max(-1.0, min(1.0, base))) * float(max(0.0, min(1.0, sig)))

class SentimentAgent:
    """
    Public interface used by src/app/main.py:
      evaluate(pair: str) -> Dict[str, Any] with keys:
        score, conf, pol, vz, sig, ts_fresh, ts
    """

    def __init__(self, ttl_sec: int = TTL_SEC) -> None:
        self.ttl_sec = ttl_sec

    def evaluate(self, pair: str) -> Dict[str, Any]:
        rec = _load_sentiment(pair)
        if rec is None:
            # No data = neutral, low confidence
            return {
                "score": 0.0,
                "conf": 0.20,
                "pol": 0.0,
                "vz": 0.0,
                "sig": 0.5,
                "ts_fresh": False,
                "ts": 0,
            }

        ts_ok = _fresh(rec.ts, self.ttl_sec)
        score = _score_from_components(rec.pol, rec.vz, rec.sig)

        # Confidence: combine freshness and declared signal strength
        freshness_boost = 0.15 if ts_ok else 0.0
        conf = max(0.0, min(1.0, 0.40 * rec.sig + freshness_boost))

        return {
            "score": float(score),
            "conf": float(conf),
            "pol": float(rec.pol),
            "vz": float(rec.vz),
            "sig": float(rec.sig),
            "ts_fresh": bool(ts_ok),
            "ts": int(rec.ts) if rec.ts else 0,
        }

# convenience factory used by main
def make_agent(ttl_sec: int = TTL_SEC) -> SentimentAgent:
    return SentimentAgent(ttl_sec=ttl_sec)
