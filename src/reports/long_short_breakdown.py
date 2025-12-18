# src/reports/long_short_breakdown.py
from __future__ import annotations
import json

TRADES_PATH = "data/backtests/backtest_trades_latest.jsonl"


def load_trades(path: str):
    rows = []
    with open(path, "r") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def compute_stats(trades):
    wins = sum(1 for t in trades if t["pnl_r"] > 0)
    losses = sum(1 for t in trades if t["pnl_r"] < 0)
    pnl_r = sum(t["pnl_r"] for t in trades)
    pnl_r_gross = sum(t.get("pnl_r_gross", t["pnl_r"]) for t in trades)

    n = len(trades)
    rr = 1.5 if n > 0 else None
    winrate = wins / n if n > 0 else 0
    expectancy_gross = pnl_r_gross / n if n > 0 else 0
    expectancy = pnl_r / n if n > 0 else 0

    # Profit Factor
    gross_gains = sum(t.get("pnl_r_gross", t["pnl_r"]) for t in trades if t.get("pnl_r_gross", t["pnl_r"]) > 0)
    gross_losses = sum(-t.get("pnl_r_gross", t["pnl_r"]) for t in trades if t.get("pnl_r_gross", t["pnl_r"]) < 0)
    pf_gross = gross_gains / gross_losses if gross_losses > 0 else None

    gains = sum(t["pnl_r"] for t in trades if t["pnl_r"] > 0)
    losses_sum = sum(-t["pnl_r"] for t in trades if t["pnl_r"] < 0)
    pf = gains / losses_sum if losses_sum > 0 else None

    return {
        "n": n,
        "wins": wins,
        "losses": losses,
        "winrate": winrate,
        "rr": rr,
        "pnl_r_gross": pnl_r_gross,
        "pnl_r": pnl_r,
        "expectancy_r_gross": expectancy_gross,
        "expectancy_r": expectancy,
        "profit_factor_gross": pf_gross,
        "profit_factor": pf,
    }


def main():
    trades = load_trades(TRADES_PATH)

    long_trades = [t for t in trades if t["side"] == "LONG"]
    short_trades = [t for t in trades if t["side"] == "SHORT"]

    result = {
        "long": compute_stats(long_trades),
        "short": compute_stats(short_trades),
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
