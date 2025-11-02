from __future__ import annotations
from datetime import datetime, timezone
import src.agents.news as news

def test_score_headline_basic():
    assert news._score_headline("ETF approval drives bullish momentum") > 0
    assert news._score_headline("Exchange hack triggers sell pressure") < 0
    assert news._score_headline("Neutral headline with no keywords") == 0

def test_run_empty(monkeypatch):
    monkeypatch.setattr(news, "CRYPTONEWS_API_KEY", "")
    agent = news.NewsAgent()
    out = agent.run(["BTCUSDT"], datetime.now(timezone.utc))
    assert len(out) == 1
    r = out[0]
    assert r["pair"] == "BTCUSDT"
    assert -1.0 <= r["score"] <= 1.0
    assert 0.0 <= r["confidence"] <= 1.0
