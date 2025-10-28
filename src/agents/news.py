from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Sequence
from src.agents.base import Agent, Candle, AgentResult

_MAX_AGE_MS = 120_000  # ≤2 min


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _fresh(ts_ms: int, now_ms: int) -> bool:
    return (now_ms - ts_ms) <= _MAX_AGE_MS


class NewsAgent(Agent):
    """
    Reads cached news sentiment from data/news/{pair}.json
    JSON: {"timestamp_ms": int, "bias": float[-1,1], "novelty": float[0,1]}
    Score = bias * (0.5 + 0.5*novelty). Confidence from recency and novelty.
    """
    def run(self, pair: str, candles: Sequence[Candle], inputs_fresh: bool) -> AgentResult:
        t0 = time.time()
        now_ms = int(t0 * 1000)
        path = Path("data") / "news" / f"{pair}.json"
        if not path.exists():
            return self._result(pair, 0.0, 0.2, "no news file", False, t0)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ts = int(data.get("timestamp_ms", 0))
            bias = float(data.get("bias", 0.0))
            novelty = float(data.get("novelty", 0.0))  # 0..1
        except Exception as e:
            return self._result(pair, 0.0, 0.2, f"bad news json: {e}", False, t0)

        fresh = _fresh(ts, now_ms)
        nov = max(0.0, min(1.0, novelty))
        amp = 0.5 + 0.5 * nov
        score = _clamp(bias * amp, -1.0, 1.0)

        conf = 0.5 + 0.3 * amp
        if not fresh:
            conf = max(0.05, conf - 0.3)

        expl = f"bias={bias:+.2f}, novelty={nov:.2f}, amp={amp:.2f}, ts_fresh={fresh}"
        return self._result(pair, float(score), float(conf), expl, fresh, t0)

    def _result(self, pair: str, score: float, conf: float, expl: str, fresh: bool, t0: float) -> AgentResult:
        return {
            "pair": pair,
            "score": float(score),
            "confidence": float(conf),
            "explanation": expl,
            "inputs_fresh": bool(fresh),
            "latency_ms": int((time.time() - t0) * 1000),
        }
