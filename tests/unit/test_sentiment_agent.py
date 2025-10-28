from pathlib import Path
import json
import time

from src.agents.sentiment import SentimentAgent


def test_sentiment_uses_cached_json(tmp_path: Path, monkeypatch):
    d = tmp_path / "data" / "sentiment"
    d.mkdir(parents=True)
    now_ms = int(time.time() * 1000)
    (d / "BTCUSDT.json").write_text(
        json.dumps({"timestamp_ms": now_ms, "polarity": 0.5, "volume_z": 1.0})
    )
    monkeypatch.chdir(tmp_path)
    agent = SentimentAgent()
    res = agent.run("BTCUSDT", [], True)
    assert -1.0 <= res["score"] <= 1.0
    assert 0.05 <= res["confidence"] <= 1.0
    assert res["inputs_fresh"] is True


def test_sentiment_missing_file_is_low_conf(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    agent = SentimentAgent()
    res = agent.run("ETHUSDT", [], True)
    assert res["confidence"] <= 0.2
    assert res["inputs_fresh"] is False
