# src/reports/agent_vs_performance.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/agent_vs_performance.json"
OUT_CSV = "data/reports/agent_vs_performance.csv"

AGENTS = ["technical", "sentiment", "news", "research"]


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


def _pnl_list_stats(trades: List[float]) -> Dict[str, Any]:
    """Erwartungswert, Winrate, Profit Factor für eine Liste von pnl_r."""
    if not trades:
        return {"n": 0, "winrate": None, "pf": None, "expectancy": None}

    n = len(trades)
    wins = sum(1 for x in trades if x > 0)

    gross_profit = sum(x for x in trades if x > 0)
    gross_loss = -sum(x for x in trades if x < 0)  # positiv

    winrate = wins / n if n > 0 else None
    expectancy = sum(trades) / n if n > 0 else None
    pf = (gross_profit / gross_loss) if gross_loss > 0 else None

    return {
        "n": n,
        "winrate": winrate,
        "pf": pf,
        "expectancy": expectancy,
    }


def analyze() -> Dict[str, Any]:
    trades = load_paper_trades()

    # buckets: agent → {"bull": [pnl_r...], "bear": [pnl_r...]}
    buckets: Dict[str, Dict[str, List[float]]] = {
        a: {"bull": [], "bear": []} for a in AGENTS
    }

    for t in trades:
        pnl_r = float(t.get("pnl_r", 0.0))
        meta = t.get("meta") or {}
        agent_outputs = meta.get("agent_outputs") or {}

        # Wenn keine Agent-Infos, Trade überspringen
        if not agent_outputs:
            continue

        for agent in AGENTS:
            a = agent_outputs.get(agent)
            if not a:
                continue
            score = float(a.get("score", 0.0))

            if score >= 0.0:
                buckets[agent]["bull"].append(pnl_r)
            else:
                buckets[agent]["bear"].append(pnl_r)

    out_agents: Dict[str, Any] = {}
    for agent in AGENTS:
        out_agents[agent] = {
            "bull": _pnl_list_stats(buckets[agent]["bull"]),
            "bear": _pnl_list_stats(buckets[agent]["bear"]),
        }

    result: Dict[str, Any] = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "paper_trades_total": len(trades),
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