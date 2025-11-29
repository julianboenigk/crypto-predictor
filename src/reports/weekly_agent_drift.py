import json
import os
from datetime import datetime, timedelta, timezone
import math

RUNS_LOG = "data/runs.log"
PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/weekly_agent_drift.json"

AGENTS = ["technical", "sentiment", "news", "research"]


def load_runs():
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


def load_trades():
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


def std(values):
    if len(values) <= 1:
        return None
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def analyze():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    runs = load_runs()
    trades = load_trades()

    # (pair, ts) → pnl
    pnl_lookup = {}
    for t in trades:
        ts = t.get("entry_ts") or t.get("timestamp") or t.get("t")
        pnl_lookup[(t.get("pair"), ts)] = t.get("pnl_r", 0.0)

    # collect stats
    out = {}

    for agent in AGENTS:
        scores = []
        confidences = []
        paired_pnl = []  # for correlation

        for r in runs:
            asof = r.get("asof")
            if not asof:
                continue

            try:
                ts = datetime.fromisoformat(asof)
            except:
                continue

            if ts < cutoff:
                continue

            agent_data = r.get("agent_outputs", {}).get(agent)
            if not agent_data:
                continue

            score = agent_data.get("score")
            conf = agent_data.get("confidence")

            if score is not None:
                scores.append(score)

            if conf is not None:
                confidences.append(conf)

            key = (r.get("pair"), asof)
            if key in pnl_lookup and score is not None:
                paired_pnl.append((score, pnl_lookup[key]))

        # correlation score ↔ pnl
        corr = None
        if len(paired_pnl) >= 3:
            xs = [x for x, _ in paired_pnl]
            ys = [y for _, y in paired_pnl]
            mx = sum(xs) / len(xs)
            my = sum(ys) / len(ys)

            num = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
            den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
            den_y = math.sqrt(sum((y - my) ** 2 for y in ys))

            if den_x > 0 and den_y > 0:
                corr = num / (den_x * den_y)

        out[agent] = {
            "n_scores": len(scores),
            "mean_score": sum(scores)/len(scores) if scores else None,
            "std_score": std(scores),
            "mean_confidence": sum(confidences)/len(confidences) if confidences else None,
            "n_pairs_for_corr": len(paired_pnl),
            "corr_score_to_pnl": corr,
        }

    os.makedirs("data/reports", exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=2)

    print("saved:", OUT_JSON)


if __name__ == "__main__":
    analyze()
