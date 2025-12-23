from __future__ import annotations
from typing import Dict, Any, List, Tuple

"""
Consensus V4 — Policy-Tightened (Step 6)

Design principles:
- Only two agents exist: technical + news_sentiment
- Technical decides direction
- News/Sentiment adjusts conviction only
- No vetoes, no learning, no dynamic weights
- Deterministic and backtest-safe
- Explicit guardrails against narrative bias
"""

# ------------------------------------------------------------------
# Static base weights (unchanged)
# ------------------------------------------------------------------
TECH_WEIGHT = 0.8
NEWS_WEIGHT = 0.2

# ------------------------------------------------------------------
# Policy parameters (explicit, deterministic)
# ------------------------------------------------------------------
TECH_MIN_ABS_SCORE = 0.20        # below this → ignore news completely
NEWS_CONFLICT_PENALTY = 0.50     # confidence multiplier if conflict
NEWS_MAX_EFFECTIVE_WEIGHT = 0.30 # hard cap on news influence


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def decide_pair(
    pair: str,
    votes: List[Dict[str, Any]],
    thresholds: Dict[str, float],
) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Input:
        votes = [
            {"agent": "technical", "score": float, "confidence": float, ...},
            {"agent": "news_sentiment", "score": float, "confidence": float, ...},
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

    # ------------------------------------------------------------------
    # HARD REQUIREMENT: technical agent must exist
    # ------------------------------------------------------------------
    if tech_vote is None:
        return 0.0, "HOLD", "NO_TECHNICAL_SIGNAL", {}

    tech_score = float(tech_vote.get("score", 0.0))
    tech_conf = float(tech_vote.get("confidence", 1.0))

    news_score = float(news_vote.get("score", 0.0)) if news_vote else 0.0
    news_conf = float(news_vote.get("confidence", 1.0)) if news_vote else 0.0

    # ------------------------------------------------------------------
    # STEP 6 POLICY APPLICATION
    # ------------------------------------------------------------------

    # Rule 1 — Technical gate
    if abs(tech_score) < TECH_MIN_ABS_SCORE:
        effective_news_weight = 0.0
        effective_news_conf = 0.0
        news_policy_note = "NEWS_DISABLED_WEAK_TECH"
    else:
        effective_news_weight = min(NEWS_WEIGHT, NEWS_MAX_EFFECTIVE_WEIGHT)
        effective_news_conf = news_conf
        news_policy_note = "NEWS_ACTIVE"

        # Rule 2 — Directional conflict
        if _sign(news_score) != _sign(tech_score):
            effective_news_conf *= NEWS_CONFLICT_PENALTY
            news_policy_note = "NEWS_CONFLICT_PENALIZED"

    # ------------------------------------------------------------------
    # Final score computation (explicit & bounded)
    # ------------------------------------------------------------------
    tech_component = TECH_WEIGHT * tech_score * tech_conf
    news_component = effective_news_weight * news_score * effective_news_conf

    final_score = tech_component + news_component
    final_score = max(-1.0, min(1.0, final_score))

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------
    if final_score >= thresholds["long"]:
        decision = "LONG"
    elif final_score <= thresholds["short"]:
        decision = "SHORT"
    else:
        decision = "HOLD"

    # ------------------------------------------------------------------
    # Reason + breakdown (fully explainable)
    # ------------------------------------------------------------------
    reason = (
        f"technical={tech_score:+.3f} (conf={tech_conf:.2f}), "
        f"news_sentiment={news_score:+.3f} (conf={effective_news_conf:.2f}), "
        f"policy={news_policy_note}, "
        f"final={final_score:+.3f}"
    )

    breakdown = {
        "technical": tech_component,
        "news_sentiment": news_component,
    }

    return final_score, decision, reason, breakdown
