# src/backtest/agent_stats.py
from __future__ import annotations
from typing import Dict, Any
from src.backtest.loader import load_runs


def agent_contributions(path: str = "data/runs.log", thr: float = 0.6) -> Dict[str, Any]:
    runs = load_runs(path)
    counted: Dict[str, int] = {}
    total_trades = 0

    for run in runs:
        for res in run.get("results", []):
            decision = res.get("decision")
            score = float(res.get("score", 0.0))
            if decision == "LONG" and score >= thr or decision == "SHORT" and score <= -thr:
                total_trades += 1
                for name, s, c in res.get("breakdown", []):
                    name_l = str(name).lower()
                    counted[name_l] = counted.get(name_l, 0) + 1

    return {
        "total_trades": total_trades,
        "agent_counts": counted,
    }
