from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from src.agents.ai_base import AIAgent
from src.agents.ai_news import fetch_cryptonews


class AIResearch(AIAgent):
    """
    Research Agent – interpretiert Makro, Narrative, Marktstruktur.
    MVP: nutzt dieselben CryptoNews-Daten wie News/Sentiment.
    """
    agent_name = "research"
    prompt_file = "ai_research_v1.txt"

    def run(self, pairs: List[str], asof: datetime) -> List[Dict[str, Any]]:
        news_data = fetch_cryptonews(pairs)
        outputs = []

        for pair in pairs:
            ext = {
                "pair": pair,
                "articles": news_data.get("articles", []),
                "timestamp": asof.isoformat(),
            }

            ao = super().run([], ext)

            outputs.append({
                "agent": self.agent_name,
                "pair": pair,
                "score": ao.score,
                "confidence": ao.confidence,
                "inputs_fresh": True,
                "raw": ao.raw,
            })

        return outputs
