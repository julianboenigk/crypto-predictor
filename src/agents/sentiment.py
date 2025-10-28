from __future__ import annotations
import json
import time
import math
from pathlib import Path
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult

_MAX_AGE_MS = 120_000  # align with universe.yaml


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _fresh(ts_ms: int, now_ms: int) -> bool:
    return (now_ms - ts_ms) <= _MAX_AGE_MS


class SentimentAgent(Agent):
    """
    Reads cached sentiment for a pair from data/sentiment/{pair}.json
    JSON schema: {"timestamp_ms": int, "polarity": float[-1,1], "volume_z": float}
    Score = polarity * sigmoid(volume_z); Confidence from recency and |volume_z|.
    Deterministic. No network calls.
    """

    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()
        now_ms = int(t0 * 1000)
        path = Path("data") / "sentiment" / f"{pair}.json"
        if not path.exists():
            return self._result(pair, 0.0, 0.2, "no sentiment file", False, t0)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = int(data.get("timestamp_ms", 0))
            pol = float(data.get("polarity", 0.0))
            vz = float(data.get("volume_z", 0.0))
        except Exception as e:
            return self._result(pair, 0.0, 0.2, f"bad sentiment json: {e}", False, t0)

        is_fresh = _fresh(ts, now_ms)
        sig = 1.0 / (1.0 + math.exp(-vz))
        raw = pol * sig
        score = _clamp(raw, -1.0, 1.0)

        conf = 0.5 + min(0.4, abs(vz) * 0.2)
        if not is_fresh:
            conf = max(0.05, conf - 0.3)

        expl = f"pol={pol:+.2f}, vz={vz:.2f}, sig={sig:.2f}, ts_fresh={is_fresh}"
        return self._result(pair, float(score), float(conf), expl, is_fresh, t0)

    def _result(self, pair: str, score: float, conf: float, expl: str, fresh: bool, t0: float) -> AgentResult:
        return {
            "pair": pair,
            "score": float(score),
            "confidence": float(conf),
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }
