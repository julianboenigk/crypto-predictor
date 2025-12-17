from __future__ import annotations
from typing import Dict, Any, List, Tuple


"""
Consensus V3 — Simplified (Step 3)

Design principles:
- Only two agents exist: technical + news_sentiment
- Technical decides direction
- News/Sentiment adjusts conviction only
- No vetoes, no dynamic weights, no learning
- Deterministic and backtest-safe
"""


TECH_WEIGHT = 0.8
NEWS_WEIGHT = 0.2


def decide_pair(
    pair: str,
    votes: List[Dict[str, Any]],
    thresholds: Dict[str, float],
) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Input:
        votes = [
            {"agent": "technical", "score": float, ...},
            {"agent": "news_sentiment", "score": float, ...},
        ]

    Output:
        (
            final_score: float,
            decision: "LONG" | "SHORT" | "HOLD",
            reason: str,
            breakdown: {
                "technical": float,
                "news_sentiment": float
            }
        )
    """

    tech_vote = None
    news_vote = None

    for v in votes:
        if v.get("agent") == "technical":
            tech_vote = v
        elif v.get("agent") == "news_sentiment":
            news_vote = v

    # --- HARD REQUIREMENT: Technical must exist ---
    if tech_vote is None:
        return 0.0, "HOLD", "NO_TECHNICAL_SIGNAL", {}

    tech_score = float(tech_vote.get("score", 0.0))
    news_score = float(news_vote.get("score", 0.0)) if news_vote else 0.0

    # --- Final score (simple, explicit) ---
    final_score = TECH_WEIGHT * tech_score + NEWS_WEIGHT * news_score
    final_score = max(-1.0, min(1.0, final_score))

    # --- Decision ---
    if final_score >= thresholds["long"]:
        decision = "LONG"
    elif final_score <= thresholds["short"]:
        decision = "SHORT"
    else:
        decision = "HOLD"

    reason = (
        f"technical={tech_score:+.3f}, "
        f"news_sentiment={news_score:+.3f}, "
        f"final={final_score:+.3f}"
    )

    breakdown = {
        "technical": tech_score,
        "news_sentiment": news_score,
    }

    return final_score, decision, reason, breakdown
