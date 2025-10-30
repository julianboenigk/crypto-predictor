from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path
import yaml

@dataclass
class Policy:
    min_score_threshold: float = 0.4
    max_atr_pct: float = 2.0
    rr_min: float = 1.5
    sl_atr_mult: float = 1.0
    tp_atr_mult: float = 1.5

def load_policy(path: str = "configs/policy.yaml") -> Policy:
    p = Path(path)
    if not p.exists():
        return Policy()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Policy(
        min_score_threshold=float(data.get("min_score_threshold", 0.4)),
        max_atr_pct=float(data.get("max_atr_pct", 2.0)),
        rr_min=float(data.get("rr_min", 1.5)),
        sl_atr_mult=float(data.get("sl_atr_mult", 1.0)),
        tp_atr_mult=float(data.get("tp_atr_mult", 1.5)),
    )

def gate_decision(side: str, S: float, context: Dict[str, Any], policy: Policy) -> tuple[bool, str]:
    """
    Returns (allowed, reason). context may include:
      atr_pct, rr_at_entry (if available), freshness flags, etc.
    """
    if abs(S) < policy.min_score_threshold:
        return False, f"score {S:.2f} below threshold {policy.min_score_threshold:.2f}"
    atrp = float(context.get("atr_pct", 0.0))
    if atrp > policy.max_atr_pct:
        return False, f"atr% {atrp:.2f} > max {policy.max_atr_pct:.2f}"
    rr = context.get("rr_at_entry")
    if rr is not None and rr < policy.rr_min:
        return False, f"rr {rr:.2f} < min {policy.rr_min:.2f}"
    if not context.get("inputs_fresh", True):
        return False, "inputs stale"
    return True, "ok"
