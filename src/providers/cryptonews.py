# src/providers/cryptonews.py
# -----------------------------------------------------------------------------
# Centralized CryptoNews API client.
# - Reads API key from CRYPTONEWS_API_KEY or (fallback) CRYPTONEWS_API_KEY
# - Exposes small helper functions used by fetchers:
#     * fetch_news_ticker(...)      -> raw JSON from /api/v1 (articles feed)
#     * fetch_sentiment_ticker(...) -> raw JSON from /api/v1/stat (daily sentiment)
# - Adds consistent timeouts, error messages, and minimal retries.
# -----------------------------------------------------------------------------

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

BASE_URL = "https://cryptonews-api.com"
_DEFAULT_TIMEOUT = 8  # seconds
_MAX_RETRIES = 2      # small safety net for transient 5xx or timeouts


def _get_api_key() -> str:
    """
    Read API key from env:
      1) CRYPTONEWS_API_KEY (preferred)
      2) CRYPTONEWS_API_KEY   (fallback for legacy setups)
    """
    load_dotenv(override=False)

    key = os.getenv("CRYPTONEWS_API_KEY") or os.getenv("CRYPTONEWS_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing API key for CryptoNews. Set CRYPTONEWS_API_KEY in your .env "
            "(or keep legacy CRYPTONEWS_API_KEY for backwards compatibility)."
        )
    return key


def _request_json(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Minimal request wrapper with tiny retry logic for robustness.
    Raises requests.HTTPError on non-2xx responses.
    """
    key = _get_api_key()
    url = f"{BASE_URL}{path}"
    final_params = dict(params or {})
    final_params["token"] = key

    last_err: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, params=final_params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            if attempt < _MAX_RETRIES:
                time.sleep(0.6 * (attempt + 1))
                continue
            raise
        except requests.HTTPError as e:
            # Let 4xx/5xx bubble up, but add a clearer message
            try:
                detail = resp.text  # type: ignore[name-defined]
            except Exception:
                detail = str(e)
            raise requests.HTTPError(
                f"HTTPError {getattr(e.response, 'status_code', '?')} on {path} "
                f"with params={final_params} :: {detail}"
            ) from e
        except Exception as e:
            last_err = e
            break

    if last_err:
        raise last_err
    # Fallback (should never reach)
    return {}


# -----------------------------------------------------------------------------
# Public helpers used by fetchers
# -----------------------------------------------------------------------------

def fetch_news_ticker(
    ticker: str,
    *,
    items: int = 50,
    date_window: str = "last60min",
    page: int = 1,
    cache: Optional[bool] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Raw articles feed for a single ticker.
    Mirrors:
      GET /api/v1?tickers=BTC&items=50&date=last60min&page=1&token=...

    Args:
        ticker: e.g. "BTC", "ETH" (NOT "BTCUSDT"; strip suffix in the caller)
        items:  number of items per page (provider caps may apply)
        date_window: one of provider’s accepted values
        page:   pagination page
        cache:  True/False to override provider caching; None leaves it unset
        timeout: request timeout

    Returns: provider JSON
    """
    params: Dict[str, Any] = {
        "tickers": ticker,
        "items": int(items),
        "date": date_window,
        "page": int(page),
    }
    if cache is not None:
        # provider expects "cache=false" or "cache=true"
        params["cache"] = "true" if cache else "false"

    return _request_json("GET", "/api/v1", params=params, timeout=timeout)


def fetch_sentiment_ticker(
    ticker: str,
    *,
    date_window: str = "last1days",
    page: int = 1,
    cache: Optional[bool] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Daily sentiment for a single ticker.
    Mirrors:
      GET /api/v1/stat?tickers=BTC&date=last1days&page=1&cache=false&token=...

    Note: Sentiment score range (per docs) is [-1.5, +1.5].
          Caller is responsible for any smoothing/transforms.

    Args:
        ticker: e.g. "BTC", "ETH"
        date_window: accepted values per docs:
                     today, yesterday, last7days, last30days, yeartodate, or ranges
        page: pagination page
        cache: True/False to override provider caching; None leaves it unset
        timeout: request timeout

    Returns: provider JSON
    """
    params: Dict[str, Any] = {
        "tickers": ticker,
        "date": date_window,
        "page": int(page),
    }
    if cache is not None:
        params["cache"] = "true" if cache else "false"

    return _request_json("GET", "/api/v1/stat", params=params, timeout=timeout)


# Optional: helpers for “all tickers” and “general” sentiment, if you need them.
def fetch_sentiment_alltickers(
    *,
    date_window: str = "last30days",
    page: int = 1,
    cache: Optional[bool] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Mirrors:
      GET /api/v1/stat?section=alltickers&date=last30days&page=1&token=...
    """
    params: Dict[str, Any] = {
        "section": "alltickers",
        "date": date_window,
        "page": int(page),
    }
    if cache is not None:
        params["cache"] = "true" if cache else "false"

    return _request_json("GET", "/api/v1/stat", params=params, timeout=timeout)


def fetch_sentiment_general(
    *,
    date_window: str = "last30days",
    page: int = 1,
    cache: Optional[bool] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """
    Mirrors:
      GET /api/v1/stat?section=general&date=last30days&page=1&token=...
    """
    params: Dict[str, Any] = {
        "section": "general",
        "date": date_window,
        "page": int(page),
    }
    if cache is not None:
        params["cache"] = "true" if cache else "false"

    return _request_json("GET", "/api/v1/stat", params=params, timeout=timeout)
