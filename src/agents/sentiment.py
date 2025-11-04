# src/agents/sentiment.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://cryptonews-api.com/api/v1/stat"
CACHE_DIR = Path("data")
CACHE_FILE = CACHE_DIR / "sentiment_cryptonews_alltickers.json"


@dataclass(frozen=True)
class TickerSentiment:
    ticker: str
    score_raw: float  # API: -1.5 .. +1.5
    ts: int           # unix seconds


class SentimentAgent:
    """
    Batch sentiment via CryptoNewsAPI /api/v1/stat?section=alltickers...

    Non-blocking policy:
    - If API/ticker missing → score=0.0, confidence=0.05, inputs_fresh=True
      so it does NOT force HOLD for the whole system.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_cache_age_sec: int = 3600,
        timeout_sec: int = 6,
        use_cache_param: bool = True,
    ) -> None:
        # try both names so we match the news agent
        self.api_key = api_key or os.getenv("CRYPTONEWS_API_KEY") or os.getenv("CRYPTONEWS_API_TOKEN")
        self.max_cache_age_sec = max_cache_age_sec
        self.timeout_sec = timeout_sec
        self.use_cache_param = use_cache_param

    def run(self, universe: List[str], asof: datetime) -> List[Dict[str, Any]]:
        t0 = time.time()
        sentiments, from_cache = self._load_all_tickers()
        latency_ms = int((time.time() - t0) * 1000)

        out: List[Dict[str, Any]] = []
        for pair in universe:
            ticker = self._pair_to_ticker(pair)
            item = sentiments.get(ticker.upper())

            if item is None:
                # IMPORTANT: non-blocking fallback
                out.append(
                    {
                        "pair": pair,
                        "agent": "sentiment",
                        "score": 0.0,
                        "confidence": 0.05,
                        "inputs_fresh": True,  # ← let other agents decide
                        "asof": asof.isoformat(),
                        "explanation": f"SentimentAgent: no sentiment for {ticker}; neutral non-blocking fallback.",
                        "latency_ms": latency_ms,
                    }
                )
                continue

            score = self._normalize_score(item.score_raw)
            confidence = self._confidence_from_raw(item.score_raw)

            if from_cache:
                age_ok = asof.replace(tzinfo=timezone.utc).timestamp() - item.ts <= self.max_cache_age_sec
                fresh = age_ok
            else:
                fresh = True

            out.append(
                {
                    "pair": pair,
                    "agent": "sentiment",
                    "score": score,
                    "confidence": confidence,
                    "inputs_fresh": fresh,
                    "asof": asof.isoformat(),
                    "explanation": (
                        f"SentimentAgent: CryptoNewsAPI score={item.score_raw:.3f} "
                        f"(norm={score:.3f}) for {ticker}, fresh={fresh}."
                    ),
                    "latency_ms": latency_ms,
                }
            )

        return out

    # ---------------- internal ----------------
    def _load_all_tickers(self) -> tuple[Dict[str, TickerSentiment], bool]:
        fetched = self._fetch_all_tickers()
        if fetched is not None:
            self._write_cache(fetched)
            return fetched, False
        cached = self._read_cache()
        if cached is not None:
            return cached, True
        return {}, False

    def _fetch_all_tickers(self) -> Optional[Dict[str, TickerSentiment]]:
        if not self.api_key:
            return None

        params = {
            "section": "alltickers",
            "date": "last30days",
            "page": 1,
            "token": self.api_key,
        }
        if self.use_cache_param:
            params["cache"] = "false"

        try:
            resp = requests.get(BASE_URL, params=params, timeout=self.timeout_sec)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return None

        return self._parse_api_payload(data)

    def _parse_api_payload(self, data: Dict[str, Any]) -> Dict[str, TickerSentiment]:
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        items = data.get("data") or data.get("stats") or data.get("results") or []

        out: Dict[str, TickerSentiment] = {}
        for item in items:
            ticker = (
                item.get("ticker")
                or item.get("symbol")
                or item.get("asset")
                or item.get("name")
            )
            if not ticker:
                continue

            raw = item.get("sentiment_score") or item.get("score") or item.get("sentiment")
            if raw is None:
                continue

            try:
                raw_f = float(raw)
            except (TypeError, ValueError):
                continue

            out[ticker.upper()] = TickerSentiment(
                ticker=ticker.upper(),
                score_raw=raw_f,
                ts=now_ts,
            )

        return out

    def _write_cache(self, mapping: Dict[str, TickerSentiment]) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            serializable = {
                k: {"ticker": v.ticker, "score_raw": v.score_raw, "ts": v.ts}
                for k, v in mapping.items()
            }
            CACHE_FILE.write_text(json.dumps(serializable), encoding="utf-8")
        except Exception:
            return

    def _read_cache(self) -> Optional[Dict[str, TickerSentiment]]:
        if not CACHE_FILE.exists():
            return None
        try:
            raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            out: Dict[str, TickerSentiment] = {}
            for k, v in raw.items():
                out[k.upper()] = TickerSentiment(
                    ticker=v["ticker"].upper(),
                    score_raw=float(v["score_raw"]),
                    ts=int(v["ts"]),
                )
            return out
        except Exception:
            return None

    @staticmethod
    def _pair_to_ticker(pair: str) -> str:
        upper = pair.upper()
        for suffix in ("USDT", "USDC", "BUSD", "EUR", "USD"):
            if upper.endswith(suffix):
                return upper[: -len(suffix)]
        return upper

    @staticmethod
    def _normalize_score(raw: float) -> float:
        norm = raw / 1.5
        if norm > 1.0:
            norm = 1.0
        if norm < -1.0:
            norm = -1.0
        return round(norm, 3)

    @staticmethod
    def _confidence_from_raw(raw: float) -> float:
        mag = abs(raw) / 1.5
        conf = 0.1 + 0.9 * mag
        if conf > 1.0:
            conf = 1.0
        return round(conf, 3)
