from __future__ import annotations
from typing import Dict, Any, List, Tuple

"""
Consensus V4 — Policy-Tightened (Step 6) + Epsilon Gate (Option A)

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

# ------------------------------------------------------------------
# Deterministic tolerance to avoid threshold edge-flapping
# ------------------------------------------------------------------
EPS = 1e-9


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
            {"agent": "technical", "pair": "...", "score": float, "confidence": float, ...},
            {"agent": "news_sentiment", "pair": "...", "score": float, "confidence": float, ...},
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
        if v.get("pair") != pair:
            continue
        if v.get("agent") == "technical":
            tech_vote = v
        elif v.get("agent") == "news_sentiment":
            news_vote = v

    # ------------------------------------------------------------------
    # HARD REQUIREMENT: technical agent must exist
    # ------------------------------------------------------------------
    if tech_vote is None:
        return 0.0, "HOLD", "NO_TECHNICAL_SIGNAL", {}

    # Safe parsing
    try:
        tech_score = float(tech_vote.get("score", 0.0))
    except Exception:
        tech_score = 0.0

    try:
        tech_conf = float(tech_vote.get("confidence", 1.0))
    except Exception:
        tech_conf = 1.0

    if news_vote:
        try:
            news_score_raw = float(news_vote.get("score", 0.0))
        except Exception:
            news_score_raw = 0.0
        try:
            news_conf_raw = float(news_vote.get("confidence", 0.0))
        except Exception:
            news_conf_raw = 0.0
    else:
        news_score_raw = 0.0
        news_conf_raw = 0.0

    # ------------------------------------------------------------------
    # STEP 6 POLICY APPLICATION
    # ------------------------------------------------------------------

    # Rule 1 — Technical gate (with EPS to avoid edge-flapping)
    if abs(tech_score) + EPS < TECH_MIN_ABS_SCORE:
        effective_news_weight = 0.0
        effective_news_conf = 0.0
        effective_news_score = 0.0
        news_policy_note = "NEWS_DISABLED_WEAK_TECH"
    else:
        effective_news_weight = min(NEWS_WEIGHT, NEWS_MAX_EFFECTIVE_WEIGHT)
        effective_news_conf = news_conf_raw
        effective_news_score = news_score_raw
        news_policy_note = "NEWS_ACTIVE"

        # Rule 2 — Directional conflict (only if news is non-zero direction)
        if _sign(effective_news_score) != 0 and _sign(effective_news_score) != _sign(tech_score):
            effective_news_conf *= NEWS_CONFLICT_PENALTY
            news_policy_note = "NEWS_CONFLICT_PENALIZED"

    # ------------------------------------------------------------------
    # Final score computation (explicit & bounded)
    # ------------------------------------------------------------------
    tech_component = TECH_WEIGHT * tech_score * tech_conf
    news_component = effective_news_weight * effective_news_score * effective_news_conf

    final_score = tech_component + news_component
    final_score = max(-1.0, min(1.0, final_score))

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------
    long_thr = float(thresholds.get("long", 0.6))
    short_thr = float(thresholds.get("short", -0.6))

    if final_score >= long_thr:
        decision = "LONG"
    elif final_score <= short_thr:
        decision = "SHORT"
    else:
        decision = "HOLD"

    # ------------------------------------------------------------------
    # Reason + breakdown (fully explainable)
    # NOTE: Reason shows EFFECTIVE news (so when disabled, score/conf become 0/0)
    # ------------------------------------------------------------------
    reason = (
        f"technical={tech_score:+.3f} (conf={tech_conf:.2f}), "
        f"news_sentiment={effective_news_score:+.3f} (conf={effective_news_conf:.2f}), "
        f"policy={news_policy_note}, "
        f"final={final_score:+.3f}"
    )

    # Optional: keep raw values visible for debugging (comment out if you don't want it)
    # reason += f" [raw_news={news_score_raw:+.3f}, raw_conf={news_conf_raw:.2f}]"

    breakdown = {
        "technical": tech_component,
        "news_sentiment": news_component,
    }

    return final_score, decision, reason, breakdown
