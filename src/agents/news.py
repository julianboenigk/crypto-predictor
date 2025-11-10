# src/agents/news.py
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
CACHE_FILE = CACHE_DIR / "news_general.json"
CACHE_TTL_SEC = int(os.getenv("NEWS_CACHE_TTL_SEC", "900"))  # 15 min

API_BASE = "https://cryptonews-api.com/api/v1/stat"
API_TOKEN = os.getenv("CRYPTO_NEWS_API_TOKEN", "yv3a4jurrsxc8ixpasmp4ug6oxnpek8zasrczrzz")


class NewsAgent:
    """
    Holt 1x die general/alltickers-News-Sentiment und verteilt es auf alle Paare.
    Damit sparen wir Calls.
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
        if (time.time() - ts) > CACHE_TTL_SEC:
            return None
        return data

    def _save_cache(self, payload: Dict[str, Any]) -> None:
        payload = dict(payload)
        payload["ts"] = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    def _fetch_general(self) -> Optional[Dict[str, Any]]:
        params = {
            "section": "general",
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

    def _score_from_item(self, item: Dict[str, Any]) -> float:
        raw = item.get("sentiment_score")
        if raw is None:
            return 0.0
        try:
            f = float(raw)
        except Exception:
            return 0.0
        f = max(-1.0, min(1.0, f / 1.5))
        return f

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
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

        # general → ein Score für den Gesamtmarkt
        # wir wenden ihn auf alle Paare an
        # wenn API mehrere Einträge schickt, nehmen wir den ersten
        data_list = data.get("data", [])
        if data_list and isinstance(data_list, list):
            base_item = data_list[0]
            sc = self._score_from_item(base_item)
            conf = 0.7
        else:
            sc = 0.0
            conf = 0.0

        out: List[Dict[str, Any]] = []
        for pair in universe:
            out.append(
                {
                    "pair": pair,
                    "agent": "news",
                    "score": sc,
                    "confidence": conf,
                    "inputs_fresh": conf > 0,
                    "asof": asof.isoformat(),
                    "explanation": "news: general market sentiment (cached)",
                }
            )

        return out
