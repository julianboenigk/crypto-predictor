# src/agents/certainty.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List

@dataclass
class Part:
    name: str
    score: float     # agent score in [-1, +1]
    conf: float      # agent confidence in [0, 1]
    fresh: bool = True  # whether this agent's data is fresh

def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

def calc_certainty(consensus_score: float, parts: List[Part]) -> float:
    """
    Heuristic certainty in [0, 100].
    Components:
      • magnitude: |S| (0..1)
      • agreement: fraction of confidence-weighted agents that agree with sign(S)
      • freshness: penalty if some parts are stale (0.9 for stale vs 1.0 fresh)
      • avg_conf: average agent confidence
    """
    S = clamp(consensus_score, -1.0, 1.0)
    mag = abs(S)  # 0..1

    if not parts:
        return round(100.0 * mag, 1)

    # weighted agreement with sign of S
    signS = 0 if S == 0 else (1 if S > 0 else -1)
    tot_w = sum(p.conf for p in parts) or 1e-9
    agree_w = sum(p.conf for p in parts if (0 if p.score == 0 else (1 if p.score > 0 else -1)) == signS)
    agreement = agree_w / tot_w  # 0..1

    # confidence & freshness
    avg_conf = sum(p.conf for p in parts) / len(parts)
    fresh_factor = sum(1.0 if p.fresh else 0.9 for p in parts) / len(parts)

    # final certainty (cap to [5, 99] for stability)
    cert = 100.0 * mag * agreement * avg_conf * fresh_factor
    return round(clamp(cert, 5.0, 99.0), 1)
