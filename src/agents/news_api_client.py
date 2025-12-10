from __future__ import annotations
import os
import time
import json
import hashlib
import requests
from typing import Dict, Any, List, Optional

"""
CryptoNews API Client (Option B)
--------------------------------
Nutzt:
- Sentiment Score
- Impact Score
- Source Credibility
- Recency Decay
- Asset-spezifische Headlines

Backtest:
- returns deterministic mock payload

Live:
- fetch + fuse → score ∈ [-1,+1], confidence ∈ [0,1]
"""


# =====================================================================
# CONFIG
# =====================================================================

API_KEY = os.getenv("CRYPTONEWS_API_KEY", "")
API_ENABLED = os.getenv("CRYPTONEWS_ENABLED", "false").lower() == "true"
WINDOW = os.getenv("CRYPTONEWS_WINDOW", "last60min")  # e.g. last60min, last24h

BASE_URL = "https://cryptonews-api.com/api/v1"


# =====================================================================
# CACHING (global in-memory)
# =====================================================================
_CACHE: Dict[str, Any] = {}
_CACHE_TTL = 60  # sekunden


def _cache_key(prefix: str, pair: str) -> str:
    token = f"{prefix}:{pair}:{WINDOW}"
    return hashlib.md5(token.encode()).hexdigest()


def _cache_get(key: str) -> Optional[Any]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    if time.time() > entry["exp"]:
        return None
    return entry["val"]


def _cache_set(key: str, value: Any):
    _CACHE[key] = {"val": value, "exp": time.time() + _CACHE_TTL}


# =====================================================================
# INTERNAL HTTP CLIENT
# =====================================================================

def _http_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP GET with retry + minimal error handling."""
    url = f"{BASE_URL}/{endpoint}"
    params["auth_token"] = API_KEY

    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=6)
            if r.status_code == 200:
                return r.json()
            time.sleep(0.5 * (attempt + 1))
        except Exception:
            time.sleep(0.5)

    return {"error": True, "data": []}


# =====================================================================
# MOCK MODUS FÜR BACKTEST
# =====================================================================

def _mock_news_payload(pair: str) -> Dict[str, Any]:
    """Deterministisch: Hash → Score."""
    h = int(hashlib.md5(pair.encode()).hexdigest(), 16) % 100
    score = ((h / 100) * 2) - 1  # [-1,+1]
    conf = 0.35 + abs(score) * 0.3
    return {
        "score": round(score, 3),
        "confidence": round(conf, 3),
        "explanation": "mock-news-score",
        "raw": {"mock": True},
    }


# =====================================================================
# FUSION LOGIK (Option B)
# =====================================================================

def _fuse_news_items(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregiert Roh-Newsdaten zu Score & Confidence.
    Verwendet:
    - headline sentiment → [-1,+1]
    - impact score → Gewichtung
    - source credibility
    - recency decay
    Formel:

        score = Σ (sentiment * impact * credibility * recency) / Σ(weights)

    confidence = min(1, 0.3 + volatility(items) + |score| * 0.4)
    """
    if not items:
        return {"score": 0.0, "confidence": 0.3}

    weighted_sum = 0.0
    weight_total = 0.0

    now = time.time()

    for n in items:
        sent = float(n.get("sentiment_score", 0.0))  # [-1,+1]
        impact = float(n.get("impact_score", 1.0))   # [0,5]
        cred = float(n.get("source_credibility", 0.5))  # [0,1]
        ts = n.get("timestamp")
        recency = 1.0

        if ts:
            age_min = max(1, (now - ts) / 60)
            recency = max(0.1, min(1.0, 1 / (age_min ** 0.3)))

        w = impact * cred * recency
        weighted_sum += sent * w
        weight_total += w

    if weight_total <= 0:
        score = 0.0
    else:
        score = weighted_sum / weight_total

    # Confidence: Mischung aus score-Stärke + Datendichte
    conf = 0.4 + min(0.6, abs(score) * 0.5 + len(items) * 0.01)

    return {
        "score": max(-1, min(1, score)),
        "confidence": max(0, min(1, conf)),
    }


# =====================================================================
# PUBLIC INTERFACES
# =====================================================================

def fetch_latest_news_signal(pair: str) -> Dict[str, Any]:
    """
    Hauptfunktion für News-Agent (Option B).
    Liefert fused Signal + Erklärung.
    """
    # Backtest Mode
    if not API_ENABLED:
        return _mock_news_payload(pair)

    key = _cache_key("news", pair)
    cached = _cache_get(key)
    if cached:
        return cached

    resp = _http_get("category", {
        "section": WINDOW,
        "items": 50,
        "tickers": pair.replace("USDT", "")
    })

    items = resp.get("data", [])
    fused = _fuse_news_items(items)

    # Erklärung
    explanation = f"{len(items)} news analyzed, score={fused['score']:.3f}, conf={fused['confidence']:.2f}"

    payload = {
        "score": fused["score"],
        "confidence": fused["confidence"],
        "explanation": explanation,
        "raw": items,
    }

    _cache_set(key, payload)
    return payload


def fetch_sentiment_signal(pair: str) -> Dict[str, Any]:
    """
    Für den Sentiment-Agent:
    - nutzt denselben Newsfeed
    - aber nur Sentiment (kein Impact, Credibility)
    """
    if not API_ENABLED:
        return _mock_news_payload(pair)

    key = _cache_key("sentiment", pair)
    cached = _cache_get(key)
    if cached:
        return cached

    resp = _http_get("category", {
        "section": WINDOW,
        "items": 50,
        "tickers": pair.replace("USDT", "")
    })

    items = resp.get("data", [])

    if not items:
        return {"score": 0.0, "confidence": 0.3, "explanation": "no news", "raw": []}

    sent_scores = [float(x.get("sentiment_score", 0.0)) for x in items]
    avg_sent = sum(sent_scores) / len(sent_scores)

    conf = min(1.0, 0.4 + abs(avg_sent) * 0.5 + len(items) * 0.01)

    payload = {
        "score": max(-1, min(1, avg_sent)),
        "confidence": conf,
        "explanation": f"{len(items)} sentiment items aggregated",
        "raw": items,
    }

    _cache_set(key, payload)
    return payload
