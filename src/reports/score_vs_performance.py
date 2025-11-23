# src/reports/score_vs_performance.py
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple, Iterable


PAPER_CLOSED_PATH = Path("data/paper_trades_closed.jsonl")


def _iter_closed_paper_trades(path: Path = PAPER_CLOSED_PATH) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    def _gen() -> Iterable[Dict[str, Any]]:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    return _gen()


def _bucket_edges() -> List[float]:
    # |score|-Buckets: [0.0–0.2), [0.2–0.4), [0.4–0.6), [0.6–0.8), [0.8–1.0+)
    return [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]


def _bucket_label(lo: float, hi: float) -> str:
    if hi >= 1.0:
        return f"[{lo:.1f}, 1.0+)"
    return f"[{lo:.1f}, {hi:.1f})"


def _assign_bucket(abs_score: float, edges: List[float]) -> int | None:
    for i in range(len(edges) - 1):
        if edges[i] <= abs_score < edges[i + 1]:
            return i
    return None


def _fmt_float(x: float | None, digits: int = 3) -> str:
    if x is None or math.isnan(x):
        return "n/a"
    return f"{x:.{digits}f}"


def _compute_correlation(xs: List[float], ys: List[float]) -> float | None:
    n = len(xs)
    if n == 0 or n != len(ys):
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    # unnormalized covariance; gleiche Normierung oben und unten ist für das Vorzeichen egal
    return cov / math.sqrt(var_x * var_y)


def main() -> None:
    edges = _bucket_edges()
    labels = [_bucket_label(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]

    # Aggregationsstrukturen
    buckets: List[Dict[str, Any]] = []
    for _ in labels:
        buckets.append(
            {
                "n_trades": 0,
                "wins": 0,
                "losses": 0,
                "unknown": 0,
                "pnl_sum": 0.0,
                "pnl_pos_sum": 0.0,
                "pnl_neg_sum": 0.0,
            }
        )

    total_trades = 0
    score_values: List[float] = []
    pnl_values: List[float] = []

    for rec in _iter_closed_paper_trades():
        meta = rec.get("meta") or {}
        score = meta.get("score")
        pnl_r = rec.get("pnl_r")

        # Score + PnL müssen beide vorhanden sein
        if score is None or pnl_r is None:
            continue

        try:
            score_f = float(score)
            pnl_f = float(pnl_r)
        except (TypeError, ValueError):
            continue

        abs_score = abs(score_f)
        idx = _assign_bucket(abs_score, edges)
        if idx is None:
            continue

        total_trades += 1
        b = buckets[idx]
        b["n_trades"] += 1
        b["pnl_sum"] += pnl_f
        if pnl_f > 0:
            b["wins"] += 1
            b["pnl_pos_sum"] += pnl_f
        elif pnl_f < 0:
            b["losses"] += 1
            b["pnl_neg_sum"] += pnl_f
        else:
            b["unknown"] += 1

        score_values.append(abs_score)
        pnl_values.append(pnl_f)

    # Kennzahlen pro Bucket berechnen
    result_bins: Dict[str, Dict[str, Any]] = {}
    for label, b in zip(labels, buckets):
        n = b["n_trades"]
        wins = b["wins"]
        losses = b["losses"]
        pnl_sum = b["pnl_sum"]
        pnl_pos = b["pnl_pos_sum"]
        pnl_neg = b["pnl_neg_sum"]

        if n > 0:
            winrate = wins / n
            expectancy = pnl_sum / n
        else:
            winrate = None
            expectancy = None

        if losses > 0 and pnl_neg < 0:
            profit_factor = pnl_pos / abs(pnl_neg) if pnl_pos > 0 else 0.0
        else:
            profit_factor = None

        result_bins[label] = {
            "n_trades": n,
            "wins": wins,
            "losses": losses,
            "unknown": b["unknown"],
            "winrate": winrate,
            "expectancy_r": expectancy,
            "profit_factor": profit_factor,
        }

    corr = _compute_correlation(score_values, pnl_values)

    summary: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "source": str(PAPER_CLOSED_PATH),
        "n_trades": total_trades,
        "pearson_abs_score_pnl_r": corr,
        "bins": result_bins,
    }

    # JSON-Output (für Logs / weitere Verarbeitung)
    print(json.dumps(summary, indent=2))

    # Zusätzlich eine kompakte menschliche Zusammenfassung
    print("\nScore vs. Performance (Buckets nach |score|):")
    for label in labels:
        b = result_bins[label]
        print(
            f"{label:12} | n={b['n_trades']:4d}, "
            f"winrate={_fmt_float(b['winrate'], 3)}, "
            f"exp={_fmt_float(b['expectancy_r'], 3)} R, "
            f"PF={_fmt_float(b['profit_factor'], 3)}"
        )
    print(f"\nPearson-Korrelation |score| ↔ pnl_r: {_fmt_float(corr, 3)}")


if __name__ == "__main__":
    main()
