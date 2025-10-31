# src/providers/cryptonews.py
from __future__ import annotations
import os
import time
import json
from typing import Any, Dict, List, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://cryptonews-api.com"

# ---------- API KEY HANDLING ----------
def _get_api_key() -> str:
    """
    Returns a usable CryptoNews API key from env:
      - CRYPTONEWS_API_KEY (preferred)
      - CRYPTONEWS_TOKEN   (legacy fallback)
    Raises with a clear message if missing or a known placeholder.
    """
    key = (os.getenv("CRYPTONEWS_API_KEY") or "").strip()
    legacy = (os.getenv("CRYPTONEWS_TOKEN") or "").strip()

    token = key or legacy
    bad_placeholders = {
        "", "REPLACE_WITH_YOUR_REAL_KEY", "YOUR_TOKEN_HERE", "None", "null"
    }
    if token in bad_placeholders or len(token) < 10:
        raise RuntimeError(
            "CryptoNews API key missing/placeholder. Set CRYPTONEWS_API_KEY in your .env "
            "(or keep legacy CRYPTONEWS_TOKEN for backwards compatibility)."
        )
    return token

# ---------- SESSION WITH RETRIES ----------
def _session(timeout: float = 10.0, total_retries: int = 3, backoff: float = 1.25) -> Tuple[requests.Session, float]:
    sess = requests.Session()
    retry = Retry(
        total=total_retries,
        read=total_retries,
        connect=total_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"])
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess, timeout

# ---------- HELPERS ----------
def _ensure_list(payload: Any) -> List[Dict[str, Any]]:
    """
    CryptoNews can return:
      - {"data": [...]} or {"news": [...]} or [...]
    This normalizes to a list of items.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], list):
            return payload["data"]
        if "news" in payload and isinstance(payload["news"], list):
            return payload["news"]
        # single object
        return [payload]
    return []

# ---------- PUBLIC: NEWS LIST ----------
def fetch_news_list(
    ticker: str,
    date_window: str = "last60min",
    items: int = 50,
    cache: bool = False,
) -> List[Dict[str, Any]]:
    """
    GET /api/v1?tickers=BTC&items=50&date=last60min&cache=false&token=...
    Returns a list of news items (normalized).
    """
    token = _get_api_key()
    sess, timeout = _session()
    params = {
        "tickers": ticker.upper(),
        "items": int(items),
        "date": date_window,
        "cache": "false" if not cache else "true",
        "token": token,
    }
    url = f"{BASE_URL}/api/v1"
    r = sess.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return _ensure_list(data)

# ---------- PUBLIC: SENTIMENT STAT ----------
def fetch_sentiment_stat(
    ticker: str,
    date_window: str = "yesterday",
    cache: bool = False,
) -> Dict[str, Any]:
    """
    GET /api/v1/stat?tickers=BTC&date=yesterday&page=1&cache=false&token=...
    Normalizes to:
      { "score": float, "positive": int, "negative": int, "neutral": int, "source": "cryptonews/stat" }
    """
    token = _get_api_key()
    sess, timeout = _session()
    params = {
        "tickers": ticker.upper(),
        "date": date_window,
        "page": 1,
        "cache": "false" if not cache else "true",
        "token": token,
    }
    url = f"{BASE_URL}/api/v1/stat"
    r = sess.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    return parse_sentiment_from_stat(payload, ticker)

def parse_sentiment_from_stat(payload: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    CryptoNews stat payload sample:
    {
      "total": {"BTC": {"Total Positive": 93, "Total Negative": 112, "Total Neutral": 8, "Sentiment Score": -0.134}},
      "data": {"2025-10-30": {"BTC": {"Neutral": 8, "Positive": 93, "Negative": 112, "sentiment_score": -0.134}}},
      "total_pages": 1
    }
    Fallbacks if fields are missing.
    """
    t = ticker.upper()
    score, pos, neg, neu = 0.0, 0, 0, 0

    if isinstance(payload, dict):
        total = payload.get("total", {})
        if isinstance(total, dict):
            tt = total.get(t, {})
            if isinstance(tt, dict):
                pos = int(tt.get("Total Positive", 0) or 0)
                neg = int(tt.get("Total Negative", 0) or 0)
                neu = int(tt.get("Total Neutral", 0) or 0)
                s = tt.get("Sentiment Score", 0.0)
                try:
                    score = float(s)
                except (TypeError, ValueError):
                    score = 0.0

        # if totals missing, try data block
        if pos == neg == neu == 0 and "data" in payload and isinstance(payload["data"], dict):
            # pick the most recent date key, if any
            try:
                most_recent_key = sorted(payload["data"].keys())[-1]
                dtk = payload["data"][most_recent_key]
                if isinstance(dtk, dict):
                    tt = dtk.get(t, {})
                    if isinstance(tt, dict):
                        pos = int(tt.get("Positive", 0) or 0)
                        neg = int(tt.get("Negative", 0) or 0)
                        neu = int(tt.get("Neutral", 0) or 0)
                        s = tt.get("sentiment_score", 0.0)
                        score = float(s or 0.0)
            except Exception:
                pass

    return {
        "score": float(score),
        "positive": int(pos),
        "negative": int(neg),
        "neutral": int(neu),
        "source": "cryptonews/stat",
    }
