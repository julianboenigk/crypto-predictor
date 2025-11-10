# src/agents/sentiment.py
from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "sentiment_alltickers.json"

# wie lange der Cache gültig ist (Sekunden)
CACHE_TTL_SEC = int(os.getenv("SENTIMENT_CACHE_TTL_SEC", "900"))  # 15 min

API_BASE = "https://cryptonews-api.com/api/v1/stat"
API_TOKEN = os.getenv("CRYPTO_NEWS_API_TOKEN", "yv3a4jurrsxc8ixpasmp4ug6oxnpek8zasrczrzz")


class SentimentAgent:
    """
    Holt 1x je Lauf die CryptoNews-Sentiment-Statistik für alle Ticker
    und mappt sie auf unsere Assets. Durch den Cache bleiben wir unter dem
    API-Limit.
    """

    def __init__(self) -> None:
        self.token = API_TOKEN

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        if not CACHE_FILE.exists():
            return None
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None
        ts = data.get("ts", 0)
        now = time.time()
        if (now - ts) > CACHE_TTL_SEC:
            return None
        return data

    def _save_cache(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["ts"] = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    def _fetch_alltickers(self) -> Optional[Dict[str, Any]]:
        params = {
            "section": "alltickers",
            "date": "last30days",
            "page": 1,
            "token": self.token,
            "cache": "false",
        }
        try:
            resp = requests.get(API_BASE, params=params, timeout=15)
        except Exception:
            return None
        if resp.status_code != 200:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    @staticmethod
    def _to_asset(pair: str) -> str:
        up = pair.upper()
        for suff in ("USDT", "USD", "BUSD", "EUR"):
            if up.endswith(suff):
                return up[: -len(suff)]
        return up

    def _score_from_item(self, item: Dict[str, Any]) -> float:
        # die API liefert "sentiment_score" in [-1.5, 1.5]
        raw = item.get("sentiment_score")
        if raw is None:
            return 0.0
        try:
            f = float(raw)
        except Exception:
            return 0.0
        # auf [-1,1] normalisieren
        f = max(-1.0, min(1.0, f / 1.5))
        return f

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        # 1) Cache versuchen
        cached = self._load_cache()
        if cached is None:
            # 2) neu holen
            fresh = self._fetch_alltickers()
            if fresh is not None:
                self._save_cache(fresh)
                data = fresh
            else:
                data = {}
        else:
            data = cached

        # Struktur laut API: { "data": [ { "ticker": "BTC", "sentiment_score": ... }, ... ] }
        items = {d.get("ticker", "").upper(): d for d in data.get("data", []) if isinstance(d, dict)}

        out: List[Dict[str, Any]] = []
        for pair in universe:
            asset = self._to_asset(pair)
            item = items.get(asset)
            if item is None:
                out.append(
                    {
                        "pair": pair,
                        "agent": "sentiment",
                        "score": 0.0,
                        "confidence": 0.05,
                        "inputs_fresh": False,  # kein Eintrag
                        "asof": asof.isoformat(),
                        "explanation": "sentiment: no entry in API",
                    }
                )
                continue
            sc = self._score_from_item(item)
            out.append(
                {
                    "pair": pair,
                    "agent": "sentiment",
                    "score": sc,
                    "confidence": 0.7,
                    "inputs_fresh": True,
                    "asof": asof.isoformat(),
                    "explanation": "sentiment: from CryptoNewsAPI (cached)",
                }
            )

        return out
