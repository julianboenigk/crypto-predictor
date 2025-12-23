# src/reports/paper_trades_summary.py
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


PAPER_FILE = Path("data/paper_trades.jsonl")


def _load_paper_trades() -> List[Dict[str, Any]]:
    if not PAPER_FILE.exists():
        return []

    trades: List[Dict[str, Any]] = []
    with PAPER_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                trades.append(rec)
            except json.JSONDecodeError:
                continue
    return trades


def _extract_score(rec: Dict[str, Any]) -> float | None:
    meta = rec.get("meta") or {}
    score = meta.get("score")
    if isinstance(score, (int, float)):
        return float(score)
    return None


def compute_paper_summary() -> Dict[str, Any]:
    trades = _load_paper_trades()
    n_total = len(trades)

    if n_total == 0:
        return {
            "n_trades": 0,
            "pairs": {},
            "sides": {},
            "score_stats": None,
        }

    pairs_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"n_trades": 0, "long": 0, "short": 0, "scores": []}
    )
    sides_stats: Dict[str, int] = defaultdict(int)
    all_scores: List[float] = []

    for rec in trades:
        pair = str(rec.get("pair", "UNKNOWN"))
        side = str(rec.get("side", "")).upper()
        score = _extract_score(rec)

        pairs_stats[pair]["n_trades"] += 1
        sides_stats[side] += 1

        if side == "LONG":
            pairs_stats[pair]["long"] += 1
        elif side == "SHORT":
            pairs_stats[pair]["short"] += 1

        if score is not None:
            pairs_stats[pair]["scores"].append(score)
            all_scores.append(score)

    # Score-Statistik je Pair berechnen
    for pair, s in pairs_stats.items():
        scores = s.pop("scores", [])
        if scores:
            s["score_min"] = min(scores)
            s["score_max"] = max(scores)
            s["score_avg"] = sum(scores) / len(scores)
        else:
            s["score_min"] = None
            s["score_max"] = None
            s["score_avg"] = None

    if all_scores:
        global_score_stats = {
            "min": min(all_scores),
            "max": max(all_scores),
            "avg": sum(all_scores) / len(all_scores),
        }
    else:
        global_score_stats = None

    return {
        "n_trades": n_total,
        "pairs": pairs_stats,
        "sides": sides_stats,
        "score_stats": global_score_stats,
    }


def build_human_summary(summary: Dict[str, Any]) -> str:
    n_trades = summary.get("n_trades", 0)
    pairs = summary.get("pairs", {})
    sides = summary.get("sides", {})
    score_stats = summary.get("score_stats")

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    lines: List[str] = []
    lines.append(f"Paper-Trading Übersicht ({now_str})")
    lines.append("")
    lines.append(f"- Gesamtzahl Paper-Trades: {n_trades}")
    lines.append(f"- Long: {sides.get('LONG', 0)}, Short: {sides.get('SHORT', 0)}")

    if score_stats:
        lines.append(
            f"- Scores (gesamt): min={score_stats['min']:.3f}, "
            f"avg={score_stats['avg']:.3f}, max={score_stats['max']:.3f}"
        )

    lines.append("")
    lines.append("Pro Paar:")
    for pair, stats in pairs.items():
        lines.append(
            f"  • {pair}: {stats['n_trades']} Trades "
            f"(Long={stats['long']}, Short={stats['short']}), "
            f"Score avg={stats['score_avg'] if stats['score_avg'] is not None else 'n/a'}"
        )

    return "\n".join(lines)


def main() -> None:
    summary = compute_paper_summary()
    print(json.dumps(summary, indent=2))

    # Wenn du später Telegram dafür nutzen willst,
    # kannst du build_human_summary hier anschließen.
    # Beispiel:
    # from src.core.notify import send_telegram
    # msg = build_human_summary(summary)
    # send_telegram(msg)


if __name__ == "__main__":
    main()
