from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence


@dataclass
class SentimentResult:
    score: float
    confidence: float
    info: Dict[str, Any]
    inputs_fresh: bool


class SentimentAgent:
    """
    File-based sentiment reader.
    Looks for data/sentiment/{PAIR}.json with shape:
      {
        "ts": 1730220000,           # unix seconds or ms (auto-detected)
        "polarity": 0.12,           # -1..+1
        "volume_z": 0.80,           # -inf..+inf (z-score-ish)
        "signal": 0.69              # 0..1 confidence-ish
      }

    If missing/stale → neutral score with low confidence.
    """

    def __init__(self, data_dir: str = "data", freshness_sec: int = 90 * 60):
        self.name = "sentiment"
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
        if ts_value > 10_000_000_000:  # ms
            ts_value = ts_value // 1000
        age = self._now() - int(ts_value)
        return age <= self.freshness_sec

    # ---------- public API ----------

    def evaluate(self, pair: str) -> SentimentResult:
        f = Path(self.data_dir) / "sentiment" / f"{pair}.json"
        rec = self._load_json(f)

        if not rec:
            # No file → neutral with low confidence
            return SentimentResult(
                score=0.0,
                confidence=0.20,
                info={"reason": "no sentiment file"},
                inputs_fresh=False,
            )

        pol = float(rec.get("polarity", 0.0))
        vz = float(rec.get("volume_z", 0.0))
        sig = float(rec.get("signal", 0.5))
        ts_val = int(rec.get("ts", 0))

        is_fresh = self._fresh(ts_val)

        # Simple mapping: polarity drives sign; volume_z/signal modulate confidence
        score = max(-1.0, min(1.0, pol))
        base_conf = 0.20 if not is_fresh else 0.30 + min(0.50, abs(vz) * 0.10) + min(0.20, sig * 0.20)
        confidence = max(0.0, min(1.0, base_conf))

        info = {
            "pol": round(pol, 2),
            "vz": round(vz, 2),
            "sig": round(sig, 2),
        }

        return SentimentResult(
            score=score,
            confidence=confidence,
            info=info,
            inputs_fresh=is_fresh,
        )
