from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from src.agents.sentiment import SentimentAgent


class DummyResp:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_sentiment_agent_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "data": [
            {"ticker": "BTC", "sentiment_score": 1.2},
            {"ticker": "ETH", "sentiment_score": -0.6},
        ]
    }

    def fake_get(url: str, params: Dict[str, Any], timeout: int) -> DummyResp:  # type: ignore[override]
        return DummyResp(payload)

    monkeypatch.setattr("src.agents.sentiment.requests.get", fake_get)

    agent = SentimentAgent(api_token="DUMMY", use_cache_param=False)
    res = agent.run(["BTCUSDT", "ETHUSDT"], now)

    assert len(res) == 2
    btc = [r for r in res if r["pair"] == "BTCUSDT"][0]
    eth = [r for r in res if r["pair"] == "ETHUSDT"][0]

    assert btc["score"] > 0
    assert btc["inputs_fresh"] is True
    assert "CryptoNewsAPI" in btc["explanation"]

    assert eth["score"] < 0
    assert eth["inputs_fresh"] is True


def test_sentiment_agent_missing_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "data": [
            {"ticker": "BTC", "sentiment_score": 0.0},
        ]
    }

    def fake_get(url: str, params: Dict[str, Any], timeout: int) -> DummyResp:  # type: ignore[override]
        return DummyResp(payload)

    monkeypatch.setattr("src.agents.sentiment.requests.get", fake_get)

    agent = SentimentAgent(api_token="DUMMY")
    res = agent.run(["SOLUSDT"], now)

    assert len(res) == 1
    assert res[0]["score"] == 0.0
    assert res[0]["inputs_fresh"] is False
    assert "neutral fallback" in res[0]["explanation"]


def test_sentiment_agent_no_token() -> None:
    agent = SentimentAgent(api_token=None)
    res = agent.run(["BTCUSDT"], datetime.now(tz=timezone.utc))
    assert res[0]["score"] == 0.0
    assert res[0]["inputs_fresh"] is False
