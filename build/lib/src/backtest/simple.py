# src/backtest/simple.py
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any


def load_signals(path: str = "data/runs.log") -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                out.append(obj)
            except Exception:
                continue
    return out


def backtest_dummy(threshold: float = 0.6) -> Dict[str, Any]:
    """
    Sehr einfacher Backtest:
    - LONG wenn decision=LONG und score>=threshold
    - SHORT wenn decision=SHORT und score<=-threshold
    - wir zählen nur Treffer/Fehlschlag nicht wirklich Kursverlauf
    """
    runs = load_signals()
    trades = 0
    longs = 0
    shorts = 0

    for run in runs:
        results = run.get("results", [])
        for res in results:
            decision = res.get("decision")
            score = float(res.get("score", 0.0))
            if decision == "LONG" and score >= threshold:
                trades += 1
                longs += 1
            elif decision == "SHORT" and score <= -threshold:
                trades += 1
                shorts += 1

    return {
        "total_runs": len(runs),
        "trades": trades,
        "longs": longs,
        "shorts": shorts,
        "threshold": threshold,
    }


if __name__ == "__main__":
    stats = backtest_dummy(0.6)
    print(json.dumps(stats, indent=2))
