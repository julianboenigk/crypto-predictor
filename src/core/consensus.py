from __future__ import annotations
from typing import Dict, Any, List
import yaml
import os

"""
Multi-Agent Consensus V2.0 (AI-ready)
------------------------------------

Aggregiert Scores & Confidences der Agents:
    final_score = Σ (score_i * weight_i * confidence_i) / Σ (weight_i * confidence_i)

Breakdown für Logging + Backtest:
    [
        (agent, score, confidence, weight, weighted),
        ...
    ]

Wenn Daten fehlen oder Agent zurückgibt score=None → Agent wird ignoriert.
"""


# ---------------------------------------------------------------------
# LOAD WEIGHTS
# ---------------------------------------------------------------------

def load_agent_weights() -> Dict[str, float]:
    path = os.path.join("src", "config", "weights.yaml")
    with open(path, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------
# MAIN CONSENSUS FUNCTION
# ---------------------------------------------------------------------

def aggregate_agent_outputs(agent_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Eingabe:
        [
            {"agent": "technical", "score": ..., "confidence": ..., "explanation": ...},
            {"agent": "news", ...},
            {"agent": "sentiment", ...},
            {"agent": "research", ...},
        ]
    Rückgabe:
        {
            "final_score": float,
            "breakdown": [...],
            "valid_agents": int
        }
    """

    weights = load_agent_weights()

    num = 0.0
    den = 0.0
    breakdown_rows = []

    for out in agent_outputs:
        agent = out.get("agent")
        score = out.get("score")
        conf = out.get("confidence", 0.0)

        if score is None or agent not in weights:
            continue

        w = float(weights.get(agent, 0.0))
        weighted = score * conf * w

        breakdown_rows.append(
            (agent, float(score), float(conf), w, weighted)
        )

        num += weighted
        den += abs(w) * max(1e-9, conf)

    if den <= 0:
        final = 0.0
    else:
        final = max(-1.0, min(1.0, num / den))

    return {
        "final_score": final,
        "breakdown": breakdown_rows,
        "valid_agents": len(breakdown_rows),
    }
