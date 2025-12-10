from __future__ import annotations

import os
import json
from typing import Any, Dict, List
from datetime import datetime, timedelta

from src.agents.ai_base import AIAgent

# ----------------------------------------------------------
# ENV
# ----------------------------------------------------------
CRYPTONEWS_ENABLED = os.getenv("CRYPTONEWS_ENABLED", "true").lower() == "true"
CRYPTONEWS_API_KEY = os.getenv("CRYPTONEWS_API_KEY")
CRYPTONEWS_WINDOW = os.getenv("CRYPTONEWS_WINDOW", "last60min")
CRYPTONEWS_ENDPOINT = "https://cryptonews-api.com/api/v1"


# ----------------------------------------------------------
# CryptoNews API
# ----------------------------------------------------------
def fetch_cryptonews(pairs: List[str]) -> Dict[str, Any]:
    if not CRYPTONEWS_ENABLED or not CRYPTONEWS_API_KEY:
        return {"articles": [], "error": "disabled_or_no_key"}

    # Time window
    now = datetime.utcnow()
    if CRYPTONEWS_WINDOW == "last60min":
        since = now - timedelta(minutes=60)
    elif CRYPTONEWS_WINDOW == "last120min":
        since = now - timedelta(minutes=120)
    else:
        since = now - timedelta(hours=24)

    ts_limit = int(since.timestamp())
    url = f"{CRYPTONEWS_ENDPOINT}/category?section=general&items=50&token={CRYPTONEWS_API_KEY}"

    try:
        import requests
        r = requests.get(url, timeout=8)
        data = r.json()
    except Exception as e:
        return {"articles": [], "error": str(e)}

    articles = []
    for a in data.get("data", []):
        try:
            pub = datetime.fromisoformat(a["date"])
            if pub.timestamp() < ts_limit:
                continue

            text = (a.get("title", "") + " " + a.get("description", "")).upper()
            if any(p.replace("USDT", "").upper() in text for p in pairs):
                articles.append(a)
        except Exception:
            continue

    return {"articles": articles, "error": None}


# ----------------------------------------------------------
# AI News Agent
# ----------------------------------------------------------
class AINews(AIAgent):
    agent_name = "news"
    prompt_file = "ai_news_v1.txt"   # <- final naming

    def run(self, pairs: List[str], asof: datetime) -> List[Dict[str, Any]]:
        news_data = fetch_cryptonews(pairs)
        outputs = []

        for pair in pairs:
            ao = super().run(
                candle_window=[],    # News benötigen keine Candles
                external_data={"pair": pair, "articles": news_data.get("articles", [])}
            )

            outputs.append({
                "agent": self.agent_name,
                "pair": pair,
                "score": ao.score,
                "confidence": ao.confidence,
                "inputs_fresh": True,
                "raw": ao.raw,
            })

        return outputs
