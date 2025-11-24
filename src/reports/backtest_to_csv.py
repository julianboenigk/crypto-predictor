# src/reports/backtest_to_csv.py
from __future__ import annotations
import csv
from pathlib import Path
from src.reports.backtest_analyzer import load_all_backtests, summarize

OUT_FILE = Path("data/backtests_summary.csv")


def main() -> None:
    bts = load_all_backtests()
    rows = [summarize(bt) for bt in bts]
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["file", "n_trades", "wins", "losses", "unknown", "winrate_pct"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"written: {OUT_FILE}")


if __name__ == "__main__":
    main()
