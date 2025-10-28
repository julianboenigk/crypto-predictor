from pathlib import Path
import json
import time

from src.agents.news import NewsAgent


def test_news_cached_json(tmp_path: Path, monkeypatch):
    d = tmp_path / "data" / "news"
    d.mkdir(parents=True)
    now = int(time.time() * 1000)
    (d / "BTCUSDT.json").write_text(
        json.dumps({"timestamp_ms": now, "bias": 0.6, "novelty": 0.5})
    )
    monkeypatch.chdir(tmp_path)
    res = NewsAgent().run("BTCUSDT", [], True)
    assert -1.0 <= res["score"] <= 1.0
    assert res["inputs_fresh"] is True
    assert res["confidence"] >= 0.5


def test_news_missing_file(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = NewsAgent().run("ETHUSDT", [], True)
    assert res["confidence"] <= 0.2
    assert res["inputs_fresh"] is False
