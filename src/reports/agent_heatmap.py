# src/reports/agent_heatmap.py
import json
import os
import numpy as np
import matplotlib.pyplot as plt

PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/agent_heatmap.json"
OUT_PNG = "data/reports/agent_heatmap.png"

# Technical score buckets
TECH_BUCKETS = [
    (-1.0, -0.6),
    (-0.6, -0.2),
    (-0.2, +0.2),
    (+0.2, +0.6),
    (+0.6, +1.0),
]

# Sentiment score buckets
SENT_BUCKETS = TECH_BUCKETS[:]   # Same bins for symmetry


def bucket(lo, hi):
    return f"{lo:.1f}…{hi:.1f}"


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


def analyze():
    trades = load_trades()

    heatmap_matrix = [
        [ [] for _ in SENT_BUCKETS ]
        for _ in TECH_BUCKETS
    ]

    # Iterate all trades
    for t in trades:
        pnl = t.get("pnl_r")
        if pnl is None:
            continue

        meta = t.get("meta") or {}
        agents = meta.get("agent_outputs") or {}

        tech = agents.get("technical", {}).get("score")
        sent = agents.get("sentiment", {}).get("score")

        if tech is None or sent is None:
            continue

        # Assign bucket indices
        tech_idx = None
        sent_idx = None

        for i, (lo, hi) in enumerate(TECH_BUCKETS):
            if lo <= tech < hi:
                tech_idx = i
                break

        for j, (lo, hi) in enumerate(SENT_BUCKETS):
            if lo <= sent < hi:
                sent_idx = j
                break

        if tech_idx is None or sent_idx is None:
            continue

        heatmap_matrix[tech_idx][sent_idx].append(pnl)

    # Compute PF per cell
    pf_matrix = []
    result_json = []

    for i, row in enumerate(heatmap_matrix):
        pf_row = []
        json_row = []

        for values in row:
            if len(values) == 0:
                pf_row.append(None)
                json_row.append(None)
                continue

            gross_profit = sum(x for x in values if x > 0)
            gross_loss = -sum(x for x in values if x < 0)
            pf = gross_profit / gross_loss if gross_loss > 0 else None

            pf_row.append(pf)
            json_row.append(pf)

        pf_matrix.append(pf_row)
        result_json.append(json_row)

    os.makedirs("data/reports", exist_ok=True)

    # Save JSON
    with open(OUT_JSON, "w") as f:
        json.dump(result_json, f, indent=2)

    # Plot heatmap
    arr = np.array([[x if x is not None else np.nan for x in row] for row in pf_matrix])

    plt.figure(figsize=(10, 8))
    plt.imshow(arr, cmap="viridis", interpolation="nearest")
    plt.title("Agent Heatmap (PF): Technical vs Sentiment")
    plt.xlabel("Sentiment Bucket")
    plt.ylabel("Technical Bucket")
    plt.colorbar(label="Profit Factor")

    plt.xticks(range(len(SENT_BUCKETS)), [bucket(lo, hi) for lo, hi in SENT_BUCKETS])
    plt.yticks(range(len(TECH_BUCKETS)), [bucket(lo, hi) for lo, hi in TECH_BUCKETS])

    plt.tight_layout()
    plt.savefig(OUT_PNG)
    plt.close()

    print("saved:", OUT_JSON, OUT_PNG)


if __name__ == "__main__":
    analyze()
