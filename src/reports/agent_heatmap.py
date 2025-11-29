import json
import os
import numpy as np
import matplotlib.pyplot as plt

PAPER_FILE = "data/paper_trades_closed.jsonl"
RUNS_LOG = "data/runs.log"
OUT_JSON = "data/reports/agent_heatmap.json"
OUT_PNG = "data/reports/agent_heatmap.png"

BUCKETS = [
    (-1.0, -0.6),
    (-0.6, -0.2),
    (-0.2, +0.2),
    (+0.2, +0.6),
    (+0.6, +1.0),
]


def bucket_index(score):
    for idx, (lo, hi) in enumerate(BUCKETS):
        if lo <= score < hi:
            return idx
    return None


def load_paper():
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


def load_runs():
    if not os.path.exists(RUNS_LOG):
        return {}
    lookup = {}
    with open(RUNS_LOG, "r") as f:
        for line in f:
            try:
                r = json.loads(line)
            except:
                continue

            pair = r.get("pair")
            ts = r.get("asof")
            if not pair or not ts:
                continue

            key = (pair, ts)
            lookup[key] = r.get("agent_outputs", {})
    return lookup


def analyze():
    trades = load_paper()
    runs = load_runs()

    # 5x5 matrix of lists
    matrix = [[[] for _ in range(5)] for _ in range(5)]

    for t in trades:
        pair = t.get("pair")
        ts = t.get("entry_ts") or t.get("timestamp") or t.get("t")
        pnl = t.get("pnl_r")

        if pair is None or ts is None or pnl is None:
            continue

        key = (pair, ts)
        agents = runs.get(key)
        if not agents:
            continue

        tech = agents.get("technical", {}).get("score")
        sent = agents.get("sentiment", {}).get("score")

        if tech is None or sent is None:
            continue

        i = bucket_index(tech)
        j = bucket_index(sent)
        if i is None or j is None:
            continue

        matrix[i][j].append(pnl)

    # compute PF matrix
    pf_matrix = [[None for _ in range(5)] for _ in range(5)]

    for i in range(5):
        for j in range(5):
            vals = matrix[i][j]
            if len(vals) < 10:
                pf_matrix[i][j] = None
                continue

            gross_profit = sum(x for x in vals if x > 0)
            gross_loss = -sum(x for x in vals if x < 0)
            pf = gross_profit / gross_loss if gross_loss > 0 else None
            pf_matrix[i][j] = pf

    # save json
    os.makedirs("data/reports", exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(pf_matrix, f, indent=2)

    # PNG heatmap
    plt.figure(figsize=(8, 6))
    data = np.array([[x if x is not None else 0 for x in row] for row in pf_matrix])
    cmap = plt.cm.viridis

    plt.imshow(data, cmap=cmap, interpolation="nearest")
    plt.title("Technical Score × Sentiment Score — PF Heatmap")
    plt.colorbar(label="Profit Factor")

    tick_labels = [f"{lo:.1f}..{hi:.1f}" for lo, hi in BUCKETS]
    plt.xticks(range(5), tick_labels, rotation=45)
    plt.yticks(range(5), tick_labels)

    plt.xlabel("Sentiment Score Bucket")
    plt.ylabel("Technical Score Bucket")
    plt.tight_layout()
    plt.savefig(OUT_PNG)
    plt.close()

    print("saved:", OUT_JSON, OUT_PNG)


if __name__ == "__main__":
    analyze()
