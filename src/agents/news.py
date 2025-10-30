from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class NewsResult:
    score: float
    confidence: float
    info: Dict[str, Any]
    inputs_fresh: bool


class NewsAgent:
    """
    File-based news signal reader.

    Looks for: data/news/{PAIR}.json
    Expected shape written by our news_refresh fetcher:
      {
        "ts": 1730220000000,        # unix ms (news_refresh writes ms; we also accept sec)
        "bias": -0.25,              # -1..+1 sentiment polarity aggregate
        "novelty": 0.10,            # 0..1 novelty ratio
        "amp": 0.50                 # 0..1 amplification/proxy for reach
      }

    If missing/stale → neutral score with low confidence.
    """

    def __init__(self, data_dir: str = "data", freshness_sec: int = 90 * 60):
        self.name = "news"
        self.data_dir = data_dir
        self.freshness_sec = freshness_sec

    # ---------- helpers ----------

    def _now(self) -> int:
        return int(time.time())

    def _load_json(self, path: Path) -> Dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _fresh(self, ts_value: int) -> bool:
        # accept seconds or milliseconds
        if ts_value > 10_000_000_000:  # looks like ms
            ts_value = ts_value // 1000
        age = self._now() - int(ts_value)
        return age <= self.freshness_sec

    # ---------- public API ----------

    def evaluate(self, pair: str) -> NewsResult:
        f = Path(self.data_dir) / "news" / f"{pair}.json"
        rec = self._load_json(f)

        if not rec:
            return NewsResult(
                score=0.0,
                confidence=0.35,
                info={"bias": 0.0, "novelty": 0.0, "amp": 0.50},
                inputs_fresh=False,
            )

        bias = float(rec.get("bias", 0.0))
        novelty = float(rec.get("novelty", 0.0))
        amp = float(rec.get("amp", 0.5))
        ts_val = int(rec.get("ts", 0))

        is_fresh = self._fresh(ts_val)

        # Scoring:
        #  - bias directly drives sign (already clipped -1..+1 upstream)
        #  - novelty lightly boosts magnitude (new info matters more)
        score = max(-1.0, min(1.0, bias)) * (1.0 + min(0.25, novelty * 0.5))
        score = max(-1.0, min(1.0, score))

        # Confidence:
        #  - base 0.35
        #  - + novelty up to +0.25
        #  - + amp up to +0.25
        #  - if stale, reduce to min(0.35, conf)
        conf = 0.35 + min(0.25, novelty * 0.5) + min(0.25, amp * 0.5)
        conf = max(0.0, min(1.0, conf))
        if not is_fresh:
            conf = min(0.35, conf)

        info = {
            "bias": round(bias, 2),
            "novelty": round(novelty, 2),
            "amp": round(amp, 2),
        }

        return NewsResult(
            score=score,
            confidence=conf,
            info=info,
            inputs_fresh=is_fresh,
        )
