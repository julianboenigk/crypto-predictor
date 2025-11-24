# src/agents/sentiment.py
from __future__ import annotations

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Cache-Verzeichnis und -Datei
CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = CACHE_DIR / "sentiment_alltickers.json"

# Cache-Gültigkeit in Sekunden (Standard: 15 Minuten)
CACHE_TTL_SEC = int(os.getenv("SENTIMENT_CACHE_TTL_SEC", "900"))  # 15 min

# CryptoNews-Stat-Endpoint für Sentiment-Analyse
API_BASE = "https://cryptonews-api.com/api/v1/stat"

# Token aus ENV (gleich wie im News-Agent)
API_TOKEN_ENV_VAR = "CRYPTONEWS_API_KEY"
API_TOKEN_DEFAULT = os.getenv(API_TOKEN_ENV_VAR, "")

# Sentinel, um zwischen "kein Argument übergeben" und "None explizit" zu unterscheiden
_DEFAULT_TOKEN_SENTINEL = object()


class SentimentAgent:
    """
    Holt 1x je Lauf die CryptoNews-Sentiment-Statistik für relevante Ticker
    (über &tickers=BTC,ETH,...) und mappt sie auf unsere Assets.

    api_token:
        - _DEFAULT_TOKEN_SENTINEL (Standardfall) → ENV (CRYPTONEWS_API_KEY)
        - None        → kein Token → neutraler Fallback, keine API-Calls (Tests)
        - ""          → explizit leer → ebenfalls neutral
        - String      → wird als Token verwendet (z. B. "DUMMY" im Test oder ENV-Token)

    use_cache_param:
        - steuert die Nutzung des lokalen Dateicaches (nur für Default-Token).
    """

    def __init__(
        self,
        api_token: Optional[str] = _DEFAULT_TOKEN_SENTINEL,  # type: ignore[assignment]
        use_cache_param: bool = True,
    ) -> None:
        # Standardfall: kein api_token-Argument → ENV-Token verwenden
        if api_token is _DEFAULT_TOKEN_SENTINEL:
            token = API_TOKEN_DEFAULT or ""
        # Tests: None/"" explizit → neutraler Fallback, ENV ignorieren
        elif api_token is None or api_token == "":
            token = ""
        else:
            token = api_token

        self.token = token
        self.use_cache_param = use_cache_param

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """
        Lokaler Dateicache.

        Für Tests mit api_token="DUMMY":
        - self.token != API_TOKEN_DEFAULT → kein Cache, immer frische Daten
          (bzw. das vom Test gemockte Response).
        """
        if not self.use_cache_param:
            return None
        if not API_TOKEN_DEFAULT:
            return None
        if self.token != API_TOKEN_DEFAULT:
            return None
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
        # Nur für den Default-Token persistent cachen
        if not API_TOKEN_DEFAULT:
            return
        if self.token != API_TOKEN_DEFAULT:
            return
        payload = dict(payload)
        payload["ts"] = time.time()
        try:
            CACHE_FILE.write_text(json.dumps(payload), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _to_asset(pair: str) -> str:
        up = pair.upper()
        for suff in ("USDT", "USD", "BUSD", "EUR"):
            if up.endswith(suff):
                return up[: -len(suff)]
        return up

    def _score_from_item(self, item: Dict[str, Any]) -> float:
        """
        Erwartet ein Feld "sentiment_score" in [-1.5, 1.5] und normalisiert auf [-1, 1].
        Dies entspricht der Struktur, die in den Unit-Tests gemockt wird.
        """
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

    def _fetch_alltickers(self, universe: List[str]) -> Optional[Dict[str, Any]]:
        """
        Holt Sentiment für alle im Universe vorkommenden Assets über
        &tickers=BTC,ETH,SOL,...

        Die reale API-Struktur (wie in deinem Test A) ist:

            {
              "total": {...},
              "data": {
                "2025-11-24": { "BTC": { ..., "sentiment_score": -0.051 }, ... },
                ...
              },
              "total_pages": 1
            }

        Diese Funktion transformiert das in das interne Format der Unit-Tests:

            {
              "data": [
                {"ticker": "BTC", "sentiment_score": ...},
                {"ticker": "ETH", "sentiment_score": ...},
                ...
              ]
            }

        Wenn die API bereits das Test-Format liefert (DummyResp in den Tests),
        wird es direkt durchgereicht.
        """
        if not self.token:
            return None

        # Relevante Assets aus dem Universe extrahieren (BTC, ETH, SOL, ...)
        assets = sorted({self._to_asset(p) for p in universe})
        if not assets:
            return None

        params: Dict[str, Any] = {
            "tickers": ",".join(assets),
            "date": "last30days",
            "page": 1,
            "token": self.token,
        }

        try:
            resp = requests.get(API_BASE, params=params, timeout=15)
        except Exception:
            return None

        try:
            payload = resp.json()
        except Exception:
            return None

        # Fall 1: Test-Payload – "data" ist bereits eine Liste von Dicts mit "ticker"/"sentiment_score"
        data_field = payload.get("data")
        if isinstance(data_field, list):
            return payload

        # Fall 2: Reale API – "data" ist ein dict[date][ticker] -> { ..., "sentiment_score": x }
        if isinstance(data_field, dict):
            flat: List[Dict[str, Any]] = []
            seen: Dict[str, bool] = {}

            # Neueste Daten zuerst: Dates absteigend sortieren
            dates = sorted(data_field.keys(), reverse=True)
            for date in dates:
                day_entry = data_field.get(date, {})
                if not isinstance(day_entry, dict):
                    continue
                for ticker in assets:
                    if ticker in seen:
                        continue
                    tinfo = day_entry.get(ticker)
                    if isinstance(tinfo, dict) and "sentiment_score" in tinfo:
                        flat.append(
                            {
                                "ticker": ticker,
                                "sentiment_score": tinfo.get("sentiment_score"),
                            }
                        )
                        seen[ticker] = True
                if len(seen) == len(assets):
                    break

            return {"data": flat}

        # Irgendein anderes, unerwartetes Format → leer zurückgeben
        return {"data": []}

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        # ---------------------------------------------------------
        # 0) Kein Token → neutraler Fallback, keine API-Calls
        # ---------------------------------------------------------
        if not self.token:
            out: List[Dict[str, Any]] = []
            for pair in universe:
                out.append(
                    {
                        "pair": pair,
                        "agent": "sentiment",
                        "score": 0.0,
                        "confidence": 0.0,
                        "inputs_fresh": False,
                        "asof": asof.isoformat(),
                        "explanation": "sentiment: neutral fallback (no API token)",
                    }
                )
            return out

        # 1) Cache versuchen (nur für Default-Token & use_cache_param=True)
        cached = self._load_cache()
        if cached is None:
            # 2) neu holen (auf Universe basierend)
            fresh = self._fetch_alltickers(universe)
            if fresh is not None:
                self._save_cache(fresh)
                data: Dict[str, Any] = fresh
            else:
                data = {}
        else:
            data = cached

        # Erwartete Struktur (Tests & Normalbetrieb): { "data": [ { "ticker": "BTC", "sentiment_score": ... }, ... ] }
        items: Dict[str, Dict[str, Any]] = {
            d.get("ticker", "").upper(): d
            for d in data.get("data", [])
            if isinstance(d, dict)
        }

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
                        "inputs_fresh": False,  # kein Eintrag für dieses Asset
                        "asof": asof.isoformat(),
                        "explanation": "sentiment: neutral fallback (no entry in API)",
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
                    "explanation": "sentiment: from CryptoNewsAPI (cached or live)",
                }
            )

        return out
