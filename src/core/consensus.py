from __future__ import annotations
from typing import Dict, List, TypedDict

import os

class Vote(TypedDict):
    agent: str
    score: float        # [-1,+1]
    confidence: float   # [0,1]
    explanation: str

class Decision(TypedDict):
    consensus: float
    decision: str       # LONG | SHORT | HOLD
    reason: str

DEFAULT_THRESHOLDS = {
    "long": float(os.getenv("CONSENSUS_LONG", os.getenv("FINAL_SCORE_MIN", "0.6"))),
    "short": float(os.getenv("CONSENSUS_SHORT", "-" + os.getenv("FINAL_SCORE_MIN", "0.6"))),
}

def decide(votes: List[Vote], weights: Dict[str, float] | None = None,
           thresholds: Dict[str, float] | None = None) -> Decision:
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    if not votes:
        return {"consensus": 0.0, "decision": "HOLD", "reason": "no votes"}

    w = weights or {}
    num = 0.0
    den = 0.0
    parts: List[str] = []
    for v in votes:
        a = v["agent"]
        ww = float(w.get(a, 1.0))
        eff = v["score"] * max(0.0, min(1.0, v["confidence"]))
        num += ww * eff
        den += abs(ww)
        parts.append(f"{a}={eff:+.2f}×w{ww:g}")

    s = num / den if den > 0 else 0.0
    if s >= thresholds["long"]:
        d = "LONG"
    elif s <= thresholds["short"]:
        d = "SHORT"
    else:
        d = "HOLD"
    reason = f"S={s:+.3f} from " + ", ".join(parts)
    return {"consensus": float(s), "decision": d, "reason": reason}
