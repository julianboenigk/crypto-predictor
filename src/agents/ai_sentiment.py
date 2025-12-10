from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from src.agents.ai_base import AIAgent
from src.agents.ai_news import fetch_cryptonews


class AISentiment(AIAgent):
    """
    Sentiment Agent – bewertet Tonalität aus News (MVP).
    """
    agent_name = "sentiment"
    prompt_file = "ai_sentiment_v1.txt"

    def run(self, pairs: List[str], asof: datetime) -> List[Dict[str, Any]]:
        news_data = fetch_cryptonews(pairs)
        outputs = []

        for pair in pairs:
            ao = super().run(
                candle_window=[],
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
