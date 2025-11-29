import json
import os
from datetime import datetime, timezone
from collections import defaultdict

PAPER_FILE = "data/paper_trades_closed.jsonl"
RUNS_LOG = "data/runs.log"
OUT_JSON = "data/reports/agent_vs_performance.json"
OUT_CSV = "data/reports/agent_vs_performance.csv"

AGENTS = ["technical", "sentiment", "news", "research"]


def load_paper_trades():
    if not os.path.exists(PAPER_FILE):
        return []
    out = []
    with open(PAPER_FILE, "r") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except:
                continue
    return out


def load_runs_log():
    if not os.path.exists(RUNS_LOG):
        return []
    out = []
    with open(RUNS_LOG, "r") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except:
                continue
    return out


def build_agent_lookup(runs_log):
    """
    Map (pair, timestamp) → agent scores.
    """
    lookup = {}
    for r in runs_log:
        key = (r.get("pair"), r.get("asof"))
        lookup[key] = r.get("agent_outputs", {})
    return lookup


def analyze():
    paper = load_paper_trades()
    runs = load_runs_log()
    lookup = build_agent_lookup(runs)

    # buckets: agent → bullish/bearish → trades
    stats = {a: {"bull": [], "bear": []} for a in AGENTS}

    for t in paper:
        pair = t.get("pair")
        asof = t.get("entry_ts") or t.get("timestamp") or t.get("t")
        pnl_r = t.get("pnl_r", 0.0)

        key = (pair, asof)
        agent_data = lookup.get(key)
        if not agent_data:
            continue

        for agent in AGENTS:
            a = agent_data.get(agent)
            if not a:
                continue

            score = a.get("score", 0.0)

            if score >= 0.0:
                stats[agent]["bull"].append(pnl_r)
            else:
                stats[agent]["bear"].append(pnl_r)

    # aggregate
    result = {}

    for agent in AGENTS:
        result[agent] = {}

        for cat in ["bull", "bear"]:
            trades = stats[agent][cat]
            if not trades:
                result[agent][cat] = {
                    "n": 0,
                    "winrate": None,
                    "pf": None,
                    "expectancy": None,
                }
                continue

            n = len(trades)
            wins = sum(1 for x in trades if x > 0)
            losses = sum(1 for x in trades if x < 0)
            gross_profit = su_
