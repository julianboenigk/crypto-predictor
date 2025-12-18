# src/reports/score_vs_performance_v2.py

import json
import os
import matplotlib.pyplot as plt

PAPER_FILE = "data/paper_trades_closed.jsonl"
OUT_JSON = "data/reports/score_vs_performance_v2.json"
OUT_CSV = "data/reports/score_vs_performance_v2.csv"
OUT_PNG = "data/reports/score_vs_performance_v2.png"

BUCKETS = [
    (-1.0, -0.6),
    (-0.6, -0.2),
    (-0.2, +0.2),
    (+0.2, +0.6),
    (+0.6, +1.0),
]


def bucket_name(lo, hi):
    return f"{lo:.1f}…{hi:.1f}"


def load_paper():
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


def extract_score(t: dict):
    """
    Robust score extraction supporting all past and current trade formats.
    """

    meta = t.get("meta", {})

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


def extract_pnl(t: dict):
    """
    Robust PnL extraction across formats.
    """

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
    trades = load_paper()

    if len(trades) < 20:
        print("WARNING: not enough paper trades for meaningful analysis.")

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

    # Compute stats
    result = {}
    pf_values = []
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
            pf_values.append(0)
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

        pf_values.append(pf if pf is not None else 0)
        labels.append(name)

    os.makedirs("data/reports", exist_ok=True)

    with open(OUT_JSON, "w") as f:
        json.dump(result, f, indent=2)

    with open(OUT_CSV, "w") as f:
        f.write("bucket,n,pf,winrate,expectancy\n")
        for k, v in result.items():
            f.write(
                f"{k},{v['n']},{v['pf']},{v['winrate']},{v['expectancy']}\n"
            )

    plt.figure(figsize=(10, 5))
    plt.bar(labels, pf_values, color="dodgerblue")
    plt.title("Score vs Performance (PF per Bucket)")
    plt.ylabel("Profit Factor")
    plt.xlabel("Score Bucket")
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(OUT_PNG)
    plt.close()

    print("saved:", OUT_JSON, OUT_CSV, OUT_PNG)


if __name__ == "__main__":
    analyze()
