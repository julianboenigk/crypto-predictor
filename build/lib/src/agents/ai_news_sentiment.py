# src/agents/ai_news_sentiment.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List

from src.core.llm import simple_completion


class AINewsSentimentAgent:
    """
    Combined News + Sentiment agent.
    Purpose:
    - Provide short-term narrative / sentiment bias
    - Never decide direction on its own
    - Only scale conviction
    """

    agent_name = "news_sentiment"

    def run(self, pairs: List[str], asof: datetime) -> List[Dict[str, Any]]:
        """
        One OpenAI call per run.
        Returns neutral output if no signal is detected.
        """

        system_prompt = """
You are a crypto market analyst.

Task:
Assess whether the CURRENT market narrative and sentiment
SUPPORTS, WEAKENS, or is NEUTRAL towards existing technical setups.

Rules:
- You do NOT predict price targets.
- You do NOT override technical analysis.
- You focus on short-term narrative (hours to 1–2 days).
- If there is no clear or actionable narrative: return NEUTRAL.

Output requirements:
Return a JSON object with per-pair entries:
{
  "<PAIR>": {
    "score": float between -1.0 and +1.0,
    "confidence": float between 0.0 and 1.0
  }
}

Interpretation:
+ score > 0  → narrative supports continuation
+ score < 0  → narrative weakens setup
+ score = 0  → no usable signal
""".strip()

        user_prompt = f"""
Pairs to evaluate:
{", ".join(pairs)}

Timestamp (UTC):
{asof.isoformat()}
""".strip()

        raw = simple_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_env_var="OPENAI_MODEL_NEWS_SENTIMENT",
            default_model="gpt-4.1-mini",
            max_tokens=600,
            temperature=0.2,
            context="news_sentiment",
        )

        outputs: Dict[str, Dict[str, float]] = {}
        try:
            import json
            outputs = json.loads(raw)
        except Exception:
            outputs = {}

        results: List[Dict[str, Any]] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for pair in pairs:
            obj = outputs.get(pair, {})
            score = float(obj.get("score", 0.0))
            confidence = float(obj.get("confidence", 0.0))

            # Defensive clamping
            score = max(-1.0, min(1.0, score))
            confidence = max(0.0, min(1.0, confidence))

            results.append({
                "agent": self.agent_name,
                "pair": pair,
                "score": score,
                "confidence": confidence,
                "inputs_fresh": True,
                "t": now_iso,
            })

        return results
