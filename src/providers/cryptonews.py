# src/providers/cryptonews.py
# -*- coding: utf-8 -*-
"""
CryptoNews provider wrapper.
- Reads API key from CRYPTONEWS_API_KEY or (fallback) CRYPTONEWS_TOKEN
- Provides:
    * fetch_news_list(...)           -> raw payload from /api/v1
    * fetch_sentiment_stat(...)      -> raw payload from /api/v1/stat
    * parse_sentiment_from_stat(...) -> normalized sentiment dict

Notes on date windows
---------------------
NEWS endpoint (/api/v1): supports time windows like
  last5min, last10min, last15min, last30min, last45min, last60min,
  today, yesterday, last7days, last30days, last60days, last90days, yeartodate

STAT endpoint (/api/v1/stat): DOES NOT accept "last1days".
Instead, use one of:
  today, yesterday, last7days, last30days, last60days, last90days, yeartodate

We normalize a few common variants:
  "last1days"   -> "yesterday"
  "last24h"     -> "yesterday"
  "last60min"   -> "today"  (for stat only; provider requires broader windows)
"""

from __future__ import annotations

import os
import time
import json
import pathlib
from typing import Any, Dict, Optional, Iterable

import requests


# ---------- Configuration ----------
BASE_URL = "https://cryptonews-api.com"
USER_AGENT = "python-requests/2.x (crypto-predictor)"
REQUEST_TIMEOUT_SEC = 20
MAX_RETRIES = 4
RETRY_BACKOFF_SEC = 1.0

CACHE_DIR = pathlib.Path("data/.cache/cryptonews")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Helpers ----------
def _get_api_key() -> str:
    key = os.getenv("CRYPTONEWS_API_KEY") or os.getenv("CRYPTONEWS_TOKEN")
    if not key or key.strip() in {"YOUR_TOKEN_HERE", "REPLACE_WITH_YOUR_REAL_KEY"}:
        raise RuntimeError(
            "CryptoNews API key missing/placeholder. Set CRYPTONEWS_API_KEY in your .env "
            "(or keep legacy CRYPTONEWS_TOKEN for backwards compatibility)."
        )
    return key.strip()


def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
    # Simple deterministic key
    ordered = "|".join(f"{k}={params[k]}" for k in sorted(params))
    return f"{endpoint}|{ordered}"


def _cache_path(endpoint: str, params: Dict[str, Any]) -> pathlib.Path:
    return CACHE_DIR / (str(abs(hash(_cache_key(endpoint, params)))) + ".json")


def _maybe_load_cache(endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    p = _cache_path(endpoint, params)
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _maybe_store_cache(endpoint: str, params: Dict[str, Any], payload: Dict[str, Any]) -> None:
    p = _cache_path(endpoint, params)
    with p.open("w", encoding="utf-8") as f:
        json.dump(payload, f)


def _http_get(endpoint: str, params: Dict[str, Any], *, cache: bool) -> Dict[str, Any]:
    """
    GET with light retries + optional on-disk caching.
    """
    if cache:
        cached = _maybe_load_cache(endpoint, params)
        if cached is not None:
            return cached

    url = BASE_URL + endpoint
    headers = {"User-Agent": USER_AGENT}
    last_err: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
            resp.raise_for_status()
            data = resp.json()
            if cache:
                _maybe_store_cache(endpoint, params, data)
            return data
        except requests.exceptions.HTTPError as e:
            # Surface provider error body if present for easier debugging
            try:
                err_body = resp.text  # type: ignore[name-defined]
            except Exception:
                err_body = str(e)
            last_err = requests.exceptions.HTTPError(
                f"HTTPError {getattr(resp, 'status_code', '?')} on {endpoint} "
                f"with params={params} :: {err_body}"
            )
            # 4xx usually won't improve with retries unless it's a transient 429
            if getattr(resp, "status_code", 0) in (401, 403, 404, 422):
                break
        except Exception as e:
            last_err = e
        time.sleep(min(RETRY_BACKOFF_SEC * attempt, 3.0))

    # Exhausted retries
    if last_err:
        raise last_err
    raise RuntimeError("Unknown error in _http_get")


# ---------- Date-window normalization ----------
_ALLOWED_STAT_WINDOWS: Iterable[str] = (
    "today",
    "yesterday",
    "last7days",
    "last30days",
    "last60days",
    "last90days",
    "yeartodate",
)

def _normalize_stat_window(w: str) -> str:
    """
    Normalize common variants into STAT-accepted values.
    """
    w = (w or "").strip().lower()

    if w in _ALLOWED_STAT_WINDOWS:
        return w

    # common variants -> normalize
    if w in {"last1days", "last24h", "last24hours"}:
        return "yesterday"
    if w in {"last60min", "last45min", "last30min", "last15min", "last10min", "last5min"}:
        # STAT doesn't accept minute windows -> use today (closest)
        return "today"

    # default fallback
    return "yesterday"


# ---------- Public API: NEWS ----------
def fetch_news_list(
    ticker: str,
    *,
    date_window: str = "last60min",
    items: int = 50,
    page: int = 1,
    cache: bool = True,
) -> Dict[str, Any]:
    """
    Calls: GET /api/v1?tickers=BTC&items=50&date=last60min&page=1&cache=false&token=...
    Returns provider payload (dict).
    """
    token = _get_api_key()
    params = {
        "tickers": ticker.upper(),
        "items": int(items),
        "date": date_window,
        "page": int(page),
        "cache": "false" if not cache else "true",
        "token": token,
    }
    return _http_get("/api/v1", params, cache=cache)


# ---------- Public API: STAT (sentiment aggregates) ----------
def fetch_sentiment_stat(
    ticker: str,
    *,
    date_window: str = "yesterday",
    page: int = 1,
    cache: bool = True,
) -> Dict[str, Any]:
    """
    Calls: GET /api/v1/stat?tickers=BTC&date=yesterday&page=1&cache=false&token=...
    Returns provider payload (dict).
    """
    token = _get_api_key()
    norm_date = _normalize_stat_window(date_window)
    params = {
        "tickers": ticker.upper(),
        "date": norm_date,
        "page": int(page),
        "cache": "false" if not cache else "true",
        "token": token,
    }
    return _http_get("/api/v1/stat", params, cache=cache)


# ---------- Parsing helpers ----------
def _first_key(d: Dict[str, Any]) -> Optional[str]:
    """Return the 'latest' key if sortable (e.g., a date string), otherwise an arbitrary first key."""
    if not d:
        return None
    try:
        return sorted(d.keys())[-1]
    except Exception:
        for k in d:
            return k
    return None


def parse_sentiment_from_stat(payload: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Extracts numeric sentiment score and counts from CryptoNews STAT payload.

    Searches in order:
      1) payload['total'][<TICKER>]['Sentiment Score']
      2) payload['data'][<date>][<TICKER>]['sentiment_score']

    Also tries to read positive/negative/neutral counts when present, handling key
    naming differences across sections.
    """
    tkr = ticker.upper()
    score: Optional[float] = None
    pos = neg = neu = None

    # Path 1: top-level 'total'
    total = payload.get("total", {})
    if isinstance(total, dict) and tkr in total and isinstance(total[tkr], dict):
        block = total[tkr]
        if "Sentiment Score" in block:
            try:
                score = float(block["Sentiment Score"])
            except Exception:
                pass
        pos = block.get("Total Positive", pos)
        neg = block.get("Total Negative", neg)
        neu = block.get("Total Neutral",  neu)

    # Path 2: per-date 'data'
    data = payload.get("data")
    if score is None and isinstance(data, dict):
        date_key = _first_key(data)
        if date_key:
            per_date = data.get(date_key, {})
            if isinstance(per_date, dict) and tkr in per_date and isinstance(per_date[tkr], dict):
                block = per_date[tkr]
                if "sentiment_score" in block:
                    try:
                        score = float(block["sentiment_score"])
                    except Exception:
                        pass
                pos = block.get("Positive", pos)
                neg = block.get("Negative", neg)
                neu = block.get("Neutral",  neu)

    # normalize counts to int if present
    def _to_int(x):
        try:
            return int(x)
        except Exception:
            return None

    pos, neg, neu = _to_int(pos), _to_int(neg), _to_int(neu)

    # final fallback for score
    if score is None:
        score = 0.0

    # clamp score to [-1, 1]
    score = max(-1.0, min(1.0, float(score)))

    return {
        "score": score,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "source": "cryptonews/stat",
    }


# ---------- CLI quick test ----------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="CryptoNews provider quick test")
    ap.add_argument("--mode", choices=["news", "stat", "both"], default="stat")
    ap.add_argument("--ticker", default="BTC")
    ap.add_argument("--news_window", default="last60min")
    ap.add_argument("--stat_window", default="yesterday")
    ap.add_argument("--items", type=int, default=10)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--cache", choices=["true", "false"], default="false")
    args = ap.parse_args()

    use_cache = args.cache.lower() == "true"

    if args.mode in ("news", "both"):
        try:
            news = fetch_news_list(
                args.ticker,
                date_window=args.news_window,
                items=args.items,
                page=args.page,
                cache=use_cache,
            )
            print("=== NEWS payload keys ===")
            print(list(news.keys())[:10])
        except Exception as e:
            print("NEWS error:", e)

    if args.mode in ("stat", "both"):
        try:
            stat = fetch_sentiment_stat(
                args.ticker,
                date_window=args.stat_window,
                page=args.page,
                cache=use_cache,
            )
            parsed = parse_sentiment_from_stat(stat, args.ticker)
            print("=== STAT parsed ===")
            print(parsed)
        except Exception as e:
            print("STAT error:", e)
