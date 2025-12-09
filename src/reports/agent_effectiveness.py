# src/reports/agent_effectiveness.py

from __future__ import annotations
import json
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

TRADES_PATH = "data/backtests/backtest_trades_latest.jsonl"


def load_trades() -> List[Dict[str, Any]]:
    trades = []
    with open(TRADES_PATH, "r") as f:
        for line in f:
            trades.append(json.loads(line))
    return trades


def compute_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {"n": 0, "wins": 0, "losses": 0, "winrate": None, "avg_pnl_r": None}

    pnls = [t["pnl_r"] for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)

    return {
        "n": len(trades),
        "wins": wins,
        "losses": losses,
        "winrate": wins / len(trades),
        "avg_pnl_r": float(np.mean(pnls)),
    }


def extract_agent_entries(t: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Erwartet breakdown-Format:
    [
        ["technical", score, confidence],
        ["sentiment", score, confidence],
        ...
    ]
    """
    out = []
    breakdown = t.get("meta", {}).get("breakdown", [])
    for entry in breakdown:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        agent = entry[0]
        score = entry[1]
        conf = entry[2] if len(entry) > 2 else 0.0

        out.append({"agent": agent, "score": score, "confidence": conf, "trade": t})

    return out


def analyze_agent(trades: List[Dict[str, Any]], agent_name: str) -> Dict[str, Any]:
    rows = []
    for t in trades:
        for ao in extract_agent_entries(t):
            if ao["agent"] == agent_name:
                rows.append(ao)

    if not rows:
        return {"agent": agent_name, "error": "no data"}

    # Buckets
    buckets = defaultdict(list)
    for ao in rows:
        score = ao["score"]
        trade = ao["trade"]

        if score >= 0.8:
            b = "[0.8,1.0]"
        elif score >= 0.6:
            b = "[0.6,0.8)"
        elif score >= 0.4:
            b = "[0.4,0.6)"
        elif score >= 0.2:
            b = "[0.2,0.4)"
        elif score >= 0.0:
            b = "[0.0,0.2)"
        elif score >= -0.2:
            b = "[-0.2,0.0)"
        elif score >= -0.4:
            b = "[-0.4,-0.2)"
        elif score >= -0.6:
            b = "[-0.6,-0.4)"
        elif score >= -0.8:
            b = "[-0.8,-0.6)"
        else:
            b = "[-1.0,-0.8]"

        buckets[b].append(trade)

    bucket_stats = {b: compute_stats(trs) for b, trs in buckets.items()}

    return {
        "agent": agent_name,
        "total_samples": len(rows),
        "buckets": bucket_stats,
    }


def main():
    trades = load_trades()

    # Agent-Namen aus breakdown extrahieren
    sample = None
    for t in trades:
        bd = t.get("meta", {}).get("breakdown", [])
        if bd:
            sample = bd
            break

    if not sample:
        print("[ERROR] No breakdowns found")
        return

    agents = set(entry[0] for entry in sample if isinstance(entry, list))

    results = {}
    for agent in agents:
        print(f"[Analyzing agent]: {agent}")
        results[agent] = analyze_agent(trades, agent)

    out_path = "data/reports/agent_effectiveness.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print("[DONE]", out_path)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
