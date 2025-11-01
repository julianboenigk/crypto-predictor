# src/app/main.py
# -----------------------------------------------------------------------------
# Crypto Predictor — Main Execution Script
# Gathers all agent signals, computes consensus, certainty, and builds
# actionable trade plans.
# -----------------------------------------------------------------------------

from __future__ import annotations
import os, json, sys
from datetime import datetime, timezone

# === Import internal modules ===
from src.agents.certainty import Part, calc_certainty
from src.agents.trade_plan import Metrics, build_plan
from src.agents import technical, sentiment, news, research  # your existing modules

DATA_DIR = os.path.join(os.getcwd(), "data")
LOG_PATH = os.path.join(DATA_DIR, "logs", "main.log")
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


# --------------------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------------------

def _log(msg: str):
    """Print + flush immediately for cron logs."""
    print(msg, flush=True)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_json(path: str, obj: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


# --------------------------------------------------------------------------
# Core execution
# --------------------------------------------------------------------------

def evaluate_pair(pair: str) -> dict:
    """Run all agents for one symbol pair and build plan."""
    _log(f"\n=== {pair} ===")

    # --- Technical Agent ---
    tech_res = technical.evaluate(pair)
    tech_score = tech_res["score"]
    tech_conf = tech_res["conf"]
    price = tech_res["price"]
    ema200 = tech_res["ema200"]
    atr_pct = tech_res["atr_pct"]
    rsi14 = tech_res.get("rsi14", 50.0)

    _log(f"[TECH] {pair} score={tech_score:+.2f} conf={tech_conf:.2f}")

    # --- Sentiment Agent ---
    sent_res = sentiment.evaluate(pair)
    sent_score = sent_res["score"]
    sent_conf = sent_res["conf"]
    sent_ts_fresh = sent_res.get("fresh", True)
    _log(f"[SENT] {pair} score={sent_score:+.2f} conf={sent_conf:.2f}")

    # --- News Agent ---
    news_res = news.evaluate(pair)
    news_score = news_res["score"]
    news_conf = news_res["conf"]
    news_ts_fresh = news_res.get("fresh", True)
    _log(f"[NEWS] {pair} score={news_score:+.2f} conf={news_conf:.2f}")

    # --- Research Agent ---
    rsch_res = research.evaluate(pair)
    rsch_score = rsch_res["score"]
    rsch_conf = rsch_res["conf"]
    _log(f"[RSCH] {pair} score={rsch_score:+.2f} conf={rsch_conf:.2f}")

    # --- Consensus Calculation ---
    w_tech, w_sent, w_news, w_rsch = 0.45, 0.20, 0.20, 0.15
    consensus_score = (
        tech_score * w_tech +
        sent_score * w_sent +
        news_score * w_news +
        rsch_score * w_rsch
    )
    _log(f"[CONSENSUS] {pair} S={consensus_score:+.3f}")

    # --- Certainty Calculation ---
    parts = [
        Part("technical", tech_score, tech_conf, True),
        Part("sentiment", sent_score, sent_conf, sent_ts_fresh),
        Part("news", news_score, news_conf, news_ts_fresh),
        Part("research", rsch_score, rsch_conf, True),
    ]
    certainty_pct = calc_certainty(consensus_score, parts)
    _log(f"[CERTAINTY] {pair} {certainty_pct:.1f}%")

    # --- Build Trade Plan ---
    metrics = Metrics(price=price, ema200=ema200, atr_pct=atr_pct, rsi14=rsi14)
    plan = build_plan(pair, consensus_score, metrics)
    plan.certainty_pct = certainty_pct

    plan_path = os.path.join(DATA_DIR, "plans", f"{pair}.json")
    _save_json(plan_path, plan.__dict__)

    _log(
        f"[PLAN] {pair} {plan.action} S={consensus_score:+.3f} "
        f"CERT={certainty_pct:.1f}% entry={plan.entry} sl={plan.stop} "
        f"tp1={plan.tp1} tp2={plan.tp2} valid_until={plan.valid_until}"
    )

    # --- Return summary for notifier ---
    return {
        "pair": pair,
        "consensus_score": consensus_score,
        "certainty_pct": certainty_pct,
        "action": plan.action,
        "plan_path": plan_path,
    }


def run_once() -> None:
    """Run all pairs once."""
    universe = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
    _log(f"Run start { _timestamp() } :: {len(universe)} pairs")

    results = []
    for pair in universe:
        try:
            results.append(evaluate_pair(pair))
        except Exception as e:
            _log(f"[ERROR] {pair}: {type(e).__name__}({e})")

    # summary
    buys = sum(1 for r in results if r["action"] == "BUY")
    sells = sum(1 for r in results if r["action"] == "SELL")
    holds = sum(1 for r in results if r["action"] == "HOLD")
    _log(f"\n[SUMMARY] BUY={buys} HOLD={holds} SELL={sells}")
    _log(f"Run end { _timestamp() }")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> int:
    try:
        run_once()
        return 0
    except Exception as e:
        _log(f"[FATAL] {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
