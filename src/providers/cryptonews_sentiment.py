from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

# Optional: load .env if python-dotenv is available. (Our shell wrapper also exports .env)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

DATA_DIR = Path("data")
SENT_DIR = DATA_DIR / "sentiment"
SENT_DIR.mkdir(parents=True, exist_ok=True)

# Keep in sync with your main config universe
PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]

BASE_URL = "https://cryptonews-api.com/api/v1/stat"
API_KEY_ENV = "CRYPTONEWS_API_KEY"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _norm_sent(raw: float) -> float:
    """
    CryptoNews sentiment is in [-1.5, +1.5]. Normalize to [-1, +1].
    """
    val = raw / 1.5
    return max(-1.0, min(1.0, val))


def _request_stat(params: Dict[str, str]) -> Dict[str, Any]:
    """
    Perform the HTTP GET and return JSON (or raise for HTTP errors).
    """
    r = requests.get(BASE_URL, params=params, timeout=12)
    r.raise_for_status()
    return r.json()


def _fetch_sentiment_for_ticker(ticker: str, token: str) -> Optional[Dict[str, Any]]:
    """
    Calls /api/v1/stat for <ticker>.
    Strategy:
      1) try date=today
      2) if no data, try date=yesterday
    Returns dict with keys: polarity, volume_z, signal; or None if still no data.
    """
    params = {
        "tickers": ticker,
        "date": "today",
        "page": "1",
        "cache": "false",
        "token": token,
    }

    try:
        payload = _request_stat(params)
        data = payload.get("data") or []
        # If API returns validation errors (e.g., wrong date format), surface them early
        if not data and payload.get("errors"):
            # Fallback directly to yesterday on empty with errors key present
            pass
        if not data:
            # Fallback to yesterday
            params["date"] = "yesterday"
            payload = _request_stat(params)
            data = payload.get("data") or []
    except requests.HTTPError as e:
        # Re-raise to be handled by caller (we want HTTP 4xx/5xx logged with full body)
        raise e

    if not data:
        return None

    # Use the latest row
    d = data[0]

    # Robust parsing
    raw_score = float(d.get("sentiment", 0.0))
    total = int(d.get("total_articles", 0))
    pos = int(d.get("positive", 0))
    neg = int(d.get("negative", 0))

    # Normalize polarity
    polarity = _norm_sent(raw_score)

    # Volume proxy -> clamp to [-3, +3]
    # Baseline and stdev are gentle defaults; adjust post-calibration if needed.
    volume_z = (total - 100) / 50.0
    volume_z = max(-3.0, min(3.0, volume_z))

    # Signal strength: more non-neutral = stronger confidence (0.4..0.9)
    signal = 0.4 + 0.5 * min(1.0, (pos + neg) / 200.0)
    signal = max(0.0, min(1.0, signal))

    return {
        "polarity": round(polarity, 3),
        "volume_z": round(volume_z, 2),
        "signal": round(signal, 2),
    }


def refresh_all() -> int:
    token = os.getenv(API_KEY_ENV, "").strip()
    if not token:
        print(f"[SENT-REFRESH][ERROR] missing env {API_KEY_ENV}")
        return 1

    for pair in PAIRS:
        ticker = pair.replace("USDT", "")
        try:
            res = _fetch_sentiment_for_ticker(ticker, token)
            if not res:
                print(f"[SENT-REFRESH][WARN] {pair}: no data returned for today/yesterday")
                continue

            out = {
                "ts": _now_ms(),
                "polarity": res["polarity"],
                "volume_z": res["volume_z"],
                "signal": res["signal"],
            }
            out_path = SENT_DIR / f"{pair}.json"
            out_path.write_text(json.dumps(out), encoding="utf-8")
            print(
                f"[SENT-REFRESH] {pair} pol={out['polarity']:+.2f} "
                f"vz={out['volume_z']:+.2f} sig={out['signal']:.2f} -> {out_path}"
            )
        except requests.HTTPError as e:
            # Print server response body to aid debugging auth/plan/date issues
            body = ""
            try:
                body = e.response.text
            except Exception:
                body = str(e)
            print(f"[SENT-REFRESH][ERROR] {pair}: HTTPError {body}")
        except Exception as e:
            print(f"[SENT-REFRESH][ERROR] {pair}: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(refresh_all())
