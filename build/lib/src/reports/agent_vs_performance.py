# src/reports/agent_vs_performance.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Iterable


PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/agent_vs_performance.json"
OUT_CSV = "data/reports/agent_vs_performance.csv"

# Frozen MVP agent universe
AGENTS = ["technical", "news_sentiment"]


# ------------------------------------------------------------------
# Load trades
# ------------------------------------------------------------------
def load_paper_trades() -> List[Dict[str, Any]]:
    if not os.path.exists(PAPER_FILE):
        return []

    out: List[Dict[str, Any]] = []
    with open(PAPER_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


# ------------------------------------------------------------------
# Stats helper
# ------------------------------------------------------------------
def _pnl_list_stats(pnls: Iterable[float]) -> Dict[str, Any]:
    vals = list(pnls)
    if not vals:
        return {"n": 0, "winrate": None, "pf": None, "expectancy": None}

    n = len(vals)
    wins = sum(1 for x in vals if x > 0)

    gross_profit = sum(x for x in vals if x > 0)
    gross_loss = -sum(x for x in vals if x < 0)  # positive

    return {
        "n": n,
        "winrate": wins / n if n else None,
        "pf": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "expectancy": sum(vals) / n if n else None,
    }


# ------------------------------------------------------------------
# Normalize agent outputs from meta
# ------------------------------------------------------------------
def _extract_agent_scores(meta: Dict[str, Any]) -> Dict[str, float]:
    """
    Returns: agent -> score

    Supports:
    - list-based agent_outputs
    - dict-based agent_outputs
    - ignores unknown agents
    """
    raw = meta.get("agent_outputs")
    scores: Dict[str, float] = {}

    if isinstance(raw, list):
        for item in raw:
            agent = item.get("agent")
            if agent in AGENTS:
                try:
                    scores[agent] = float(item.get("score", 0.0))
                except Exception:
                    continue

    elif isinstance(raw, dict):
        for agent in AGENTS:
            item = raw.get(agent)
            if not item:
                continue
            try:
                scores[agent] = float(item.get("score", 0.0))
            except Exception:
                continue

    return scores


# ------------------------------------------------------------------
# Main analysis
# ------------------------------------------------------------------
def analyze() -> Dict[str, Any]:
    trades = load_paper_trades()

    # buckets: agent -> bull/bear -> pnl_r list
    buckets: Dict[str, Dict[str, List[float]]] = {
        a: {"bull": [], "bear": []} for a in AGENTS
    }

    skipped_no_agent_info = 0

    for t in trades:
        pnl_r = float(t.get("pnl_r", 0.0))
        meta = t.get("meta") or {}

        scores = _extract_agent_scores(meta)
        if not scores:
            skipped_no_agent_info += 1
            continue

        for agent, score in scores.items():
            side = "bull" if score >= 0.0 else "bear"
            buckets[agent][side].append(pnl_r)

    out_agents: Dict[str, Any] = {}
    for agent in AGENTS:
        out_agents[agent] = {
            "bull": _pnl_list_stats(buckets[agent]["bull"]),
            "bear": _pnl_list_stats(buckets[agent]["bear"]),
        }

    result: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "paper_trades_total": len(trades),
        "paper_trades_skipped_no_agent_info": skipped_no_agent_info,
        "agents": out_agents,
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    with open(OUT_CSV, "w", encoding="utf-8") as f:
        f.write("agent,side,n,winrate,pf,expectancy\n")
        for agent, sides in out_agents.items():
            for side in ("bull", "bear"):
                s = sides[side]
                f.write(
                    f"{agent},{side},{s['n']},{s['winrate']},{s['pf']},{s['expectancy']}\n"
                )

    return result


def main() -> None:
    res = analyze()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
