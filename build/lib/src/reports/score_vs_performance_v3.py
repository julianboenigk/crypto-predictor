# src/reports/score_vs_performance_v3.py

import json
import os
import matplotlib.pyplot as plt

PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/score_vs_performance_v3.json"
OUT_PNG = "data/reports/score_vs_performance_v3.png"

BUCKETS = [
    (-1.0, -0.6),
    (-0.6, -0.2),
    (-0.2, +0.2),
    (+0.2, +0.6),
    (+0.6, +1.0),
]


def bucket_name(lo, hi):
    return f"{lo:.1f}…{hi:.1f}"


def load_trades():
    if not os.path.exists(PAPER_FILE):
        return []
    out = []
    with open(PAPER_FILE, "r") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def extract_score(t):
    meta = t.get("meta", {})

    # Best available score field
    candidates = [
        meta.get("entry_score"),
        t.get("entry_score"),
        t.get("score"),
        meta.get("score"),
        t.get("final_score"),
    ]
    for c in candidates:
        if isinstance(c, (int, float)):
            return float(c)
    return None


def extract_pnl(t):
    meta = t.get("meta", {})
    candidates = [
        t.get("pnl_r"),
        meta.get("pnl_r"),
        t.get("pnl"),
        meta.get("pnl"),
    ]
    for c in candidates:
        if isinstance(c, (int, float)):
            return float(c)
    return None


def analyze():
    trades = load_trades()

    buckets = {bucket_name(lo, hi): [] for (lo, hi) in BUCKETS}

    for t in trades:
        score = extract_score(t)
        pnl = extract_pnl(t)

        if score is None or pnl is None:
            continue

        for lo, hi in BUCKETS:
            if lo <= score < hi:
                buckets[bucket_name(lo, hi)].append(pnl)
                break

    # Calculate metrics
    result = {}
    pf_vals = []
    wr_vals = []
    exp_vals = []
    labels = []

    for lo, hi in BUCKETS:
        name = bucket_name(lo, hi)
        values = buckets[name]
        n = len(values)

        if n == 0:
            result[name] = {
                "n": 0,
                "pf": None,
                "winrate": None,
                "expectancy": None,
            }
            pf_vals.append(0)
            wr_vals.append(0)
            exp_vals.append(0)
            labels.append(name)
            continue

        wins = sum(1 for x in values if x > 0)
        gross_profit = sum(x for x in values if x > 0)
        gross_loss = -sum(x for x in values if x < 0)

        pf = gross_profit / gross_loss if gross_loss > 0 else None
        winrate = wins / n
        expectancy = sum(values) / n

        result[name] = {
            "n": n,
            "pf": pf,
            "winrate": winrate,
            "expectancy": expectancy,
        }

        pf_vals.append(pf if pf is not None else 0)
        wr_vals.append(winrate)
        exp_vals.append(expectancy)
        labels.append(name)

    # Save JSON
    os.makedirs("data/reports", exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)

    # Plot combined figure
    fig, axes = plt.subplots(3, 1, figsize=(11, 14))

    # PF
    axes[0].bar(labels, pf_vals, color="dodgerblue")
    axes[0].set_title("Profit Factor per Score Bucket")
    axes[0].grid(axis="y", linestyle="--", alpha=0.5)

    # Winrate
    axes[1].bar(labels, wr_vals, color="darkorange")
    axes[1].set_title("Winrate per Score Bucket")
    axes[1].grid(axis="y", linestyle="--", alpha=0.5)

    # Expectancy
    axes[2].bar(labels, exp_vals, color="seagreen")
    axes[2].set_title("Expectancy (R) per Score Bucket")
    axes[2].grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(OUT_PNG)
    plt.close()

    print(f"saved: {OUT_JSON} and {OUT_PNG}")


if __name__ == "__main__":
    analyze()
