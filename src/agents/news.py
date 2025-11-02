# src/agents/news.py
from __future__ import annotations

import os
import math
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

# ========== CONFIG ==========
CRYPTONEWS_API_KEY = os.getenv("CRYPTONEWS_API_KEY", "")
CRYPTONEWS_WINDOW = os.getenv("CRYPTONEWS_WINDOW", "last60min")  # e.g. last60min, last6h, last24h
API_URL = "https://cryptonews-api.com/api/v1"

# ========== KEYWORDS ==========
_POSITIVE = {
    "bullish", "surge", "rally", "breakout", "buy", "accumulate", "upgrade",
    "strong", "growth", "institutional", "inflow", "adoption", "partnership",
    "approval", "etf", "record", "all-time", "ath", "optimism", "support",
    "rebound", "reversal", "momentum", "profit", "gain", "uptrend"
}
_NEGATIVE = {
    "bearish", "dump", "sell", "downgrade", "weak", "fall", "decline",
    "outflow", "hack", "exploit", "ban", "lawsuit", "fud", "fraud", "scam",
    "insolvency", "bankrupt", "crackdown", "risk", "resistance", "rejection",
    "delay", "recession", "loss", "fear"
}


# ========== HELPERS ==========
def _pair_to_ticker(pair: str) -> str:
    """Extracts base asset from a symbol like BTCUSDT -> BTC."""
    for q in ("USDT", "USDC", "BUSD", "EUR", "USD", "BTC", "ETH"):
        if pair.endswith(q):
            return pair[:-len(q)]
    return pair


def _score_headline(text: str) -> float:
    """Score a headline between -1 (negative) and +1 (positive)."""
    if not text:
        return 0.0
    t = text.lower()
    pos = sum(1 for w in _POSITIVE if w in t)
    neg = sum(1 for w in _NEGATIVE if w in t)
    if pos == 0 and neg == 0:
        return 0.0
    raw = (pos - neg) / max(1, pos + neg)
    return max(-1.0, min(1.0, raw))


def _fetch_articles(ticker: str, window: str, items: int = 25) -> List[Dict[str, Any]]:
    """Fetch recent articles from CryptoNews API for the given ticker."""
    if not CRYPTONEWS_API_KEY:
        print("[WARN] CRYPTONEWS_API_KEY not set.")
        return []

    params = {
        "tickers": ticker,
        "items": str(items),
        "token": CRYPTONEWS_API_KEY,
        "date": window,
        "extra-fields": "rankscore,published_at,source,domain",
        "sortby": "rank",
        "fallback": "true",
    }
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        if r.status_code != 200:
            print(f"[WARN] CryptoNews API {r.status_code}: {r.text[:150]}")
            return []
        data = r.json()
        return data.get("data", []) or data.get("news", [])
    except Exception as e:
        print(f"[WARN] fetch_articles({ticker}) failed: {e}")
        return []


def _compute_sentiment(articles: List[Dict[str, Any]]) -> Dict[str, float]:
    """Aggregate sentiment score and confidence across articles."""
    if not articles:
        return {"score": 0.0, "confidence": 0.0}

    scores = [_score_headline(a.get("title", "")) for a in articles]
    if not scores:
        return {"score": 0.0, "confidence": 0.0}

    avg_score = sum(scores) / len(scores)
    # Confidence grows with article count, decays with disagreement
    dispersion = sum((s - avg_score) ** 2 for s in scores) / len(scores)
    confidence = max(0.05, min(1.0, 1.0 / (1.0 + dispersion)))
    confidence *= min(1.0, len(scores) / 10.0)  # up to 10 articles = max confidence
    return {"score": avg_score, "confidence": confidence}


# ========== MAIN AGENT ==========
class NewsAgent:
    """Analyzes recent crypto news sentiment per coin."""

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for pair in universe:
            ticker = _pair_to_ticker(pair)
            articles = _fetch_articles(ticker, CRYPTONEWS_WINDOW)
            sentiment = _compute_sentiment(articles)

            expl = f"{len(articles)} articles, avg={sentiment['score']:+.2f}, conf={sentiment['confidence']:.2f}"

            results.append({
                "pair": pair,
                "agent": "news",
                "score": sentiment["score"],
                "confidence": sentiment["confidence"],
                "inputs_fresh": True,
                "asof": asof.isoformat(),
                "explanation": expl,
            })
        return results


# ========== QUICK TEST ==========
if __name__ == "__main__":
    agent = NewsAgent()
    out = agent.run(["BTCUSDT", "ETHUSDT"], datetime.now(timezone.utc))
    for r in out:
        print(r)
