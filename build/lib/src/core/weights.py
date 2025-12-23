# src/core/weights.py
from __future__ import annotations
from typing import Dict


def compute_dynamic_weights(base: Dict[str, float]) -> Dict[str, float]:
    """
    Dynamic weights are intentionally disabled.

    Rationale:
    - Only two agents exist (technical + news_sentiment)
    - No stable historical attribution yet
    - Determinism > adaptivity at this stage

    This function is kept for interface compatibility only.
    """
    return base
