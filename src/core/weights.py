# src/core/weights.py
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Dict, List

RUNS_PATH = Path("data/runs.log")

# wie viele Zeilen aus runs.log wir für die Gewichtung betrachten
DEFAULT_LOOKBACK_LINES = int(os.getenv("WEIGHTS_LOOKBACK_LINES", "500"))
# ab welchem absoluten Score ein Signal als “relevant” zählt
DEFAULT_SIGNAL_THR = float(os.getenv("WEIGHTS_SIGNAL_THR", "0.6"))

# Basisgewichte als Fallback (Technical dominiert)
DEFAULT_BASE_WEIGHTS: Dict[str, float] = {
    "technical": 0.60,
    "sentiment": 0.15,
    "news": 0.15,
    "research": 0.10,
}


def _tail_lines(path: Path, n: int) -> List[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return lines[-n:]


def _normalize(w: Dict[str, float]) -> Dict[str, float]:
    s = sum(w.values())
    if s <= 0:
        return w
    return {k: v / s for k, v in w.items()}


def compute_dynamic_weights(
    base: Dict[str, float] | None = None,
    runs_path: Path = RUNS_PATH,
    lookback_lines: int = DEFAULT_LOOKBACK_LINES,
    signal_thr: float = DEFAULT_SIGNAL_THR,
) -> Dict[str, float]:
    """
    Idee:
    - wir schauen in die letzten N runs
    - für jedes Pair, das |score| >= signal_thr hat, zählen wir die Agenten, die beteiligt waren
    - Agenten mit vielen Beteiligungen bekommen mehr Gewicht (multipliziert auf base)
    - am Ende normalisieren wir
    """
    if base is None:
        base = DEFAULT_BASE_WEIGHTS

    lines = _tail_lines(runs_path, lookback_lines)
    if not lines:
        return base

    agent_hits: Dict[str, float] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        for res in obj.get("results", []):
            score = float(res.get("score", 0.0))
            if abs(score) < signal_thr:
                continue
            for name, s, c in res.get("breakdown", []):
                name_l = str(name).lower()
                # Gewichtung nach Confidence
                agent_hits[name_l] = agent_hits.get(name_l, 0.0) + float(c)

    if not agent_hits:
        return base

    dyn: Dict[str, float] = {}
    for agent, base_w in base.items():
        contrib = agent_hits.get(agent, 0.0)
        dyn[agent] = base_w * (1.0 + contrib)

    for agent, contrib in agent_hits.items():
        if agent not in dyn:
            dyn[agent] = contrib

    return _normalize(dyn)
