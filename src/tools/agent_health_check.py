# src/tools/agent_health_check.py
from __future__ import annotations

import json
import time
from datetime import datetime

# Core agents
from src.agents.technical import TechnicalAgent

# AI agents
from src.agents.ai_news import AINews, fetch_cryptonews
from src.agents.ai_sentiment import AISentiment
from src.agents.ai_research import AIResearch

# LLM infra
from src.agents.ai_base import load_llm_usage, check_limits


TEST_UNIVERSE = ["BTCUSDT"]
DUMMY_CANDLES = [{"c": 50000, "h": 50500, "low": 49500, "t": 1700000000}] * 300


def check_technical():
    try:
        ta = TechnicalAgent()
        res = ta.run("BTCUSDT", DUMMY_CANDLES, inputs_fresh=True)
        return {"ok": True, "score": res["score"], "confidence": res["confidence"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_news_api():
    try:
        data = fetch_cryptonews(TEST_UNIVERSE)
        if data.get("error"):
            return {"ok": False, "error": data["error"]}
        return {"ok": True, "n_articles": len(data.get("articles", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_news_ai():
    try:
        agent = AINews()
        res = agent.run(TEST_UNIVERSE, asof=datetime.utcnow())
        r = res[0]
        return {
            "ok": True,
            "score": r["score"],
            "confidence": r["confidence"],
            "raw": str(r["raw"])[:200]
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_sentiment_ai():
    try:
        agent = AISentiment()
        res = agent.run(TEST_UNIVERSE, asof=datetime.utcnow())
        r = res[0]
        return {
            "ok": True,
            "score": r["score"],
            "confidence": r["confidence"],
            "raw": str(r["raw"])[:200]
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_research_ai():
    try:
        agent = AIResearch()
        res = agent.run(TEST_UNIVERSE, asof=datetime.utcnow())
        r = res[0]
        return {
            "ok": True,
            "score": r["score"],
            "confidence": r["confidence"],
            "raw": str(r["raw"])[:200]
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_token_limits():
    calls, tokens = load_llm_usage()
    limits_ok = check_limits(tokens_required=100)
    return {
        "ok": limits_ok,
        "calls_today": calls,
        "tokens_today": tokens,
    }


def main(return_dict: bool = False):
    t0 = time.time()

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "technical": check_technical(),
        "cryptonews_api": check_news_api(),
        "ai_news": check_news_ai(),
        "ai_sentiment": check_sentiment_ai(),
        "ai_research": check_research_ai(),
        "llm_token_limits": check_token_limits(),
        "latency_ms": int((time.time() - t0) * 1000),
    }

    if return_dict:
        return report

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
