# src/providers/cryptonews.py
# Unified CryptoNews provider with retries/backoff, strict date windows,
# API key resolution (CRYPTONEWS_API_KEY preferred; CRYPTONEWS_TOKEN fallback),
# and payload normalization for both /api/v1 (news) and /api/v1/stat (sentiment stats).

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

# --- dotenv is optional; we try to load .env gracefully without crashing if not found
try:
    from dotenv import load_dotenv
    _DOTENV_LOADED = False
    def _safe_load_dotenv() -> None:
        global _DOTENV_LOADED
        if not _DOTENV_LOADED:
            # best-effort; don't throw even if it can't locate the .env file
            try:
                load_dotenv()
            except Exception:
                pass
            _DOTENV_LOADED = True
except Exception:  # pragma: no cover
    def _safe_load_dotenv() -> None:
        pass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://cryptonews-api.com"
NEWS_PATH = "/api/v1"
STAT_PATH = "/api/v1/stat"

# Valid date windows per provider docs
_ALLOWED_WINDOWS = {
    "last5min", "last10min", "last15min", "last30min", "last45min", "last60min",
    "today", "yesterday", "last7days", "last30days", "last60days", "last90days",
    "yeartodate",
}

# Default timeout (connect, read)
_DEFAULT_TIMEOUT: Tuple[int, int] = (8, 15)

# HTTP session with retries/backoff
_SESSION: Optional[requests.Session] = None


def _session() -> requests.Session:
    """Get a process-global Session with retries and backoff."""
    global _SESSION
    if _SESSION is not None:
        return _SESSION

    s = requests.Session()
    s.headers.update({
        "User-Agent": "crypto-predictor/1.0 (+https://local) python-requests",
        "Accept": "application/json",
    })
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=0.6,  # ~0.6, 1.2, 2.4, 4.8, 9.6
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    _SESSION = s
    return s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_window(win: Optional[str]) -> str:
    """Ensure the requested date window is one of the provider-allowed values."""
    w = (win or "").lower().strip()
    if w not in _ALLOWED_WINDOWS:
        # safest default for /stat when invalid comes in
        w = "yesterday"
    return w


def _map_symbol_to_ticker(symbol_or_ticker: str) -> str:
    """
    Map 'BTCUSDT' -> 'BTC', 'ETHUSDT' -> 'ETH', etc.
    If a plain ticker like 'BTC' is passed, return as-is.
    """
    s = symbol_or_ticker.upper().strip()
    if len(s) > 3 and s.endswith("USDT"):
        return s[:-4]  # drop 'USDT'
    # If it looks like 'BTC-USD' or 'BTCUSD', just take the leading letters
    if "-" in s:
        s = s.split("-")[0]
    # trim trailing non-letters
    while s and not s[-1].isalpha():
        s = s[:-1]
    return s


def _safe_int(x: Any) -> int:
    try:
        return int(x)
    except Exception:
        return 0


def _get_api_key() -> str:
    """
    Read API key from environment. Prefer CRYPTONEWS_API_KEY.
    Fall back to CRYPTONEWS_TOKEN for legacy setups.
    Reject placeholders like REPLACE_WITH_YOUR_REAL_KEY.
    """
    _safe_load_dotenv()
    key = os.getenv("CRYPTONEWS_API_KEY")
    if not key:
        key = os.getenv("CRYPTONEWS_TOKEN")

    if not key or key.strip().upper().startswith("REPLACE_WITH_YOUR_REAL_KEY"):
        raise RuntimeError(
            "CryptoNews API key missing/placeholder. Set CRYPTONEWS_API_KEY "
            "in your .env (or keep legacy CRYPTONEWS_TOKEN for backwards compatibility)."
        )
    return key.strip()


def _http_get_json(path: str, params: Dict[str, Any]) -> Any:
    """
    GET helper using the retrying session. Raises for hard HTTP errors;
    returns parsed JSON on success.
    """
    url = f"{BASE_URL}{path}"
    resp = _session().get(url, params=params, timeout=_DEFAULT_TIMEOUT)
    # If the server explicitly errors with JSON body, keep the text in the exception for logs
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Attach text (best-effort) for easier debugging in logs
        text = ""
        try:
            text = resp.text[:400]
        except Exception:
            pass
        raise requests.HTTPError(f"HTTPError {resp.status_code} on {path} with params={params} :: {text}") from e
    try:
        return resp.json()
    except Exception as e:
        raise ValueError(f"Invalid JSON for {path} with params={params}") from e


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_news_list(
    symbol_or_ticker: str,
    date_window: str = "last60min",
    *,
    items: int = 50,
    page: int = 1,
    cache: bool = False,
) -> List[Dict[str, Any]]:
    """
    Fetch latest news list for a ticker (BTC, ETH, SOL...) using /api/v1.

    Returns a list of article dicts. The provider sometimes returns either:
      - {"data": [ {article...}, ... ], "total_pages": N, ...}
      - or directly a list [ {article...}, ... ]
    We normalize to a plain list in all cases.
    """
    token = _get_api_key()
    ticker = _map_symbol_to_ticker(symbol_or_ticker)
    win = _validate_window(date_window)

    params = {
        "tickers": ticker,
        "items": items,
        "date": win,
        "page": page,
        "cache": "false" if not cache else "true",
        "token": token,
    }

    payload = _http_get_json(NEWS_PATH, params)

    # Normalize
    if isinstance(payload, list):
        articles = payload
    else:
        articles = payload.get("data") or payload.get("news") or []
        if not isinstance(articles, list):
            articles = []

    return articles


def fetch_sentiment_stat(
    symbol_or_ticker: str,
    date_window: str = "yesterday",
    *,
    page: int = 1,
    cache: bool = False,
) -> Dict[str, Any]:
    """
    Fetch sentiment stats for a ticker using /api/v1/stat.

    Provider returns something like:
    {
      "total": {
        "BTC": {"Total Positive": 93, "Total Negative": 112, "Total Neutral": 8, "Sentiment Score": -0.134}
      },
      "data": { "YYYY-MM-DD": { "BTC": {... same daily split...} } },
      "total_pages": 1
    }

    We flatten into:
    {
        "score": float,
        "positive": int,
        "negative": int,
        "neutral": int,
        "source": "cryptonews/stat"
    }
    """
    token = _get_api_key()
    ticker = _map_symbol_to_ticker(symbol_or_ticker)
    win = _validate_window(date_window)

    params = {
        "tickers": ticker,
        "date": win,
        "page": page,
        "cache": "false" if not cache else "true",
        "token": token,
    }

    payload = _http_get_json(STAT_PATH, params)

    # Shape: expect payload["total"][ticker] keys
    total = {}
    if isinstance(payload, dict):
        top_total = payload.get("total") or {}
        if isinstance(top_total, dict):
            total = top_total.get(ticker) or {}

    pos = _safe_int(total.get("Total Positive"))
    neg = _safe_int(total.get("Total Negative"))
    neu = _safe_int(total.get("Total Neutral"))
    score = total.get("Sentiment Score")
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0

    return {
        "score": score,
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "source": "cryptonews/stat",
    }


def parse_sentiment_from_stat(stat: Dict[str, Any]) -> Tuple[float, float, float]:
    """
    Convert the stat dict returned by fetch_sentiment_stat into
    (polarity, velocity, signal). Velocity is 0.0 here (single window).
    Signal is mapped from score to [0..1] via a simple logistic-like curve.
    """
    score = 0.0
    try:
        score = float(stat.get("score", 0.0))
    except Exception:
        score = 0.0

    # Polarity uses the raw provider score (already in ~[-1..+1] range).
    polarity = max(-1.0, min(1.0, score))

    # Velocity: 0.0 for single snapshot (we could add day-over-day later).
    velocity = 0.0

    # Map polarity (-1..+1) into [0..1] "signal" where 0.5 is neutral.
    # Simple linear map for now: sig = 0.5 + polarity/2
    signal = 0.5 + (polarity / 2.0)
    signal = max(0.0, min(1.0, signal))

    return polarity, velocity, signal


# Backward-compatible names (if older code imported these)
def fetch_news_ticker(symbol_or_ticker: str, date_window: str = "last60min", **kwargs) -> List[Dict[str, Any]]:
    """Alias to fetch_news_list for legacy imports."""
    return fetch_news_list(symbol_or_ticker, date_window, **kwargs)
