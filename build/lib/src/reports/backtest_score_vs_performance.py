# src/reports/backtest_score_vs_performance.py

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple


def load_trades(path: str) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            trades.append(json.loads(line))
    return trades


def bucket_for_score(score: float) -> str:
    """
    Bucket-Definition, symmetrisch um 0.
    """
    edges = [-1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    labels: List[Tuple[float, float]] = list(zip(edges[:-1], edges[1:]))

    for lo, hi in labels:
        if lo <= score < hi:
            return f"[{lo:+.1f},{hi:+.1f})"
    return "[nan,nan)"


def compute_score_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"n": 0, "wins": 0, "losses": 0, "pnl_r_sum": 0.0}
    )

    for t in trades:
        meta = t.get("meta", {})
        score = meta.get("entry_score")
        pnl_r = t.get("pnl_r")

        if score is None or pnl_r is None:
            continue

        try:
            s = float(score)
            p = float(pnl_r)
        except (TypeError, ValueError):
            continue

        b = bucket_for_score(s)
        stats = buckets[b]
        stats["n"] += 1
        stats["pnl_r_sum"] += p
        if p > 0:
            stats["wins"] += 1
        elif p < 0:
            stats["losses"] += 1

    # Kennzahlen ableiten
    out: Dict[str, Any] = {}
    for b, stats in sorted(buckets.items()):
        n = stats["n"]
        wins = stats["wins"]
        losses = stats["losses"]
        pnl_sum = stats["pnl_r_sum"]

        winrate = wins / n if n > 0 else None
        expectancy = pnl_sum / n if n > 0 else None

        gross_profit = wins * 1.5
        gross_loss = losses * 1.0
        pf = gross_profit / gross_loss if gross_loss > 0 else None

        out[b] = {
            "n": n,
            "wins": wins,
            "losses": losses,
            "winrate": winrate,
            "expectancy_r": expectancy,
            "profit_factor_gross": pf,
        }

    return out


def main() -> None:
    trades_path = os.getenv(
        "BACKTEST_TRADES_PATH",
        "data/backtests/backtest_trades_latest.jsonl",
    )
    trades = load_trades(trades_path)
    stats = compute_score_stats(trades)

    result = {
        "trades_path": trades_path,
        "buckets": stats,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
