# src/agents/news.py
from __future__ import annotations

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Cache für News, um API-Limit zu schonen
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "news_general.json"

NEWS_CACHE_TTL_SEC = int(os.getenv("NEWS_CACHE_TTL_SEC", "900"))  # 15 min

# CryptoNews-Endpoint für allgemeine Crypto-News
NEWS_API_BASE = "https://cryptonews-api.com/api/v1/category"

# Token aus ENV (gleich wie SentimentAgent)
CRYPTONEWS_API_KEY = os.getenv("CRYPTONEWS_API_KEY", "")


def _score_headline(headline: str) -> float:
    """
    Sehr einfache Heuristik:
    - bullish Keywords → +1
    - bearish Keywords → -1
    - gemischt → 0
    Ergebnis wird in [-1, 1] gekappt.
    """
    text = headline.lower()

    bullish = [
        "bull",
        "bullish",
        "rally",
        "surge",
        "soars",
        "breakout",
        "all-time high",
        "ath",
        "approval",
        "etf approval",
        "institutional inflows",
        "record highs",
        "optimistic",
        "strong gains",
        "momentum",
    ]
    bearish = [
	"bear",
        "bearish",
        "dump",
        "crash",
        "plunge",
        "sell-off",
        "sell off",
        "sell pressure",        # hinzugefügt
        "regulatory crackdown",
        "ban",
        "negative",
        "lawsuit",
        "hacked",               # bereits drin
        "hack",                 # hinzugefügt
        "exploit",
        "liquidation cascade",
    ]

    score = 0.0

    for w in bullish:
        if w in text:
            score += 0.5

    for w in bearish:
        if w in text:
            score -= 0.5

    if score > 1.0:
        score = 1.0
    if score < -1.0:
        score = -1.0

    return score


class NewsAgent:
    """
    Holt allgemeine Crypto-News (section=general) und leitet daraus
    einen Marktsentiment-Score ab, den wir auf alle Paare anwenden.

    api_key:
        - None  → nimmt CRYPTONEWS_API_KEY (ENV)
        - ""    → kein Key → neutraler Fallback
        - str   → explizit gesetzter Key
    """

    def __init__(self, api_key: Optional[str] = None, use_cache: bool = True) -> None:
        if api_key is None:
            self.api_key = CRYPTONEWS_API_KEY or ""
        else:
            self.api_key = api_key
        self.use_cache = use_cache

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        if not self.use_cache:
            return None
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
        ts = data.get("ts", 0)
        now = time.time()
        if (now - ts) > NEWS_CACHE_TTL_SEC:
            return None
        return data

    def _save_cache(self, payload: Dict[str, Any]) -> None:
        if not self.use_cache:
            return
        payload = dict(payload)
        payload["ts"] = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    def _fetch_general(self) -> Optional[Dict[str, Any]]:
        """
        Holt allgemeine Crypto-News. Struktur laut Doku ungefähr:

        {
          "data": [
            {"title": "...", "news_url": "...", ...},
            ...
          ],
          ...
        }

        Falls die API etwas anderes liefert, fangen wir das ab und
        fallen neutral zurück.
        """
        if not self.api_key:
            return None

        params: Dict[str, Any] = {
            "section": "general",
            "items": 50,
            "token": self.api_key,
        }

        try:
            resp = requests.get(NEWS_API_BASE, params=params, timeout=15)
        except Exception:
            return None

        try:
            return resp.json()
        except Exception:
            return None

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        # 0) Kein API-Key → kompletter neutraler Fallback
        if not self.api_key:
            out: List[Dict[str, Any]] = []
            for pair in universe:
                out.append(
                    {
                        "pair": pair,
                        "agent": "news",
                        "score": 0.0,
                        "confidence": 0.0,
                        "inputs_fresh": False,
                        "asof": asof.isoformat(),
                        "explanation": "news: neutral fallback (no API key)",
                    }
                )
            return out

        # 1) Cache versuchen
        cached = self._load_cache()
        if cached is None:
            fresh = self._fetch_general()
            if fresh is not None:
                self._save_cache(fresh)
                data = fresh
            else:
                data = {}
        else:
            data = cached

        # 2) Headlines extrahieren
        raw_list = data.get("data", [])
        headlines: List[str] = []
        if isinstance(raw_list, list):
            for item in raw_list:
                if isinstance(item, dict):
                    title = item.get("title")
                    if isinstance(title, str) and title.strip():
                        headlines.append(title.strip())

        # 3) Kein vernünftiger Input → neutraler Fallback (aber: Token war da)
        if not headlines:
            out: List[Dict[str, Any]] = []
            for pair in universe:
                out.append(
                    {
                        "pair": pair,
                        "agent": "news",
                        "score": 0.0,
                        "confidence": 0.1,
                        "inputs_fresh": False,
                        "asof": asof.isoformat(),
                        "explanation": "news: neutral fallback (no headlines from API)",
                    }
                )
            return out

        # 4) Headlines scor en und mitteln
        scores = [_score_headline(h) for h in headlines]
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        # 5) Ergebnis auf alle Paare anwenden
        out: List[Dict[str, Any]] = []
        explanation = f"news: average sentiment from {len(headlines)} headlines (cached or live)"
        for pair in universe:
            out.append(
                {
                    "pair": pair,
                    "agent": "news",
                    "score": avg_score,
                    "confidence": 0.7,
                    "inputs_fresh": True,
                    "asof": asof.isoformat(),
                    "explanation": explanation,
                }
            )

        return out
