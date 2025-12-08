# src/backtest/sweep_asymmetric_thresholds.py
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple

from src.backtest.run_latest import run_all
from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary
from src.reports.long_short_breakdown import load_trades, compute_stats

OUT_CSV = Path("data/reports/backtest_sweep_asym_thresholds.csv")
OUT_JSON = Path("data/reports/backtest_sweep_asym_thresholds.json")
TRADES_PATH = "data/backtests/backtest_trades_latest.jsonl"


def _ensure_out_dir() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)


def _set_threshold_env(long_thr: float, short_thr: float) -> None:
    """
    Setzt die relevanten ENV-Variablen für asymmetrische LONG/SHORT-Thresholds.
    """
    os.environ["TECH_DRIVER_LONG"] = f"{long_thr:.2f}"
    os.environ["TECH_DRIVER_SHORT"] = f"{short_thr:.2f}"
    os.environ["CONSENSUS_LONG"] = f"{long_thr:.2f}"
    os.environ["CONSENSUS_SHORT"] = f"{short_thr:.2f}"

    print(
        f"[*] ENV gesetzt: TECH_DRIVER_LONG={os.environ['TECH_DRIVER_LONG']}, "
        f"TECH_DRIVER_SHORT={os.environ['TECH_DRIVER_SHORT']}, "
        f"CONSENSUS_LONG={os.environ['CONSENSUS_LONG']}, "
        f"CONSENSUS_SHORT={os.environ['CONSENSUS_SHORT']}"
    )


def sweep_asym_thresholds(
    long_thresholds: List[float],
    short_thresholds: List[float],
) -> List[Dict[str, Any]]:
    """
    Testet für jede Kombination aus LONG- und SHORT-Thresholds einen kompletten Backtest
    und sammelt Gesamt- und Long/Short-spezifische Kennzahlen.
    """
    _ensure_out_dir()
    rows: List[Dict[str, Any]] = []

    combos: List[Tuple[float, float]] = [
        (lt, st) for lt in long_thresholds for st in short_thresholds
    ]

    for long_thr, short_thr in combos:
        print("\n===========================================")
        print(f"=== LONG >= {long_thr:.2f}, SHORT <= {short_thr:.2f} ===")
        print("===========================================")

        # 1) ENV für diese Kombination setzen
        _set_threshold_env(long_thr, short_thr)

        # 2) Backtest ausführen (score_min kommt aus FINAL_SCORE_MIN)
        run_all(score_min=None)

        # 3) Neueste Backtest-JSON laden + Summary berechnen
        bt_data = load_latest_backtest()
        summary = compute_pnl_summary(bt_data)

        # 4) Trades laden & Long/Short separat auswerten
        trades = load_trades(TRADES_PATH)
        long_trades = [t for t in trades if t.get("side") == "LONG"]
        short_trades = [t for t in trades if t.get("side") == "SHORT"]

        long_stats = compute_stats(long_trades)
        short_stats = compute_stats(short_trades)

        row: Dict[str, Any] = {
            "long_thr": long_thr,
            "short_thr": short_thr,
            # Gesamt-Backtest
            "file": summary.get("file"),
            "n_trades_total": summary.get("n_trades"),
            "wins_total": summary.get("wins"),
            "losses_total": summary.get("losses"),
            "winrate_total": summary.get("winrate"),
            "pnl_r_gross_total": summary.get("pnl_r_gross"),
            "expectancy_r_gross_total": summary.get("expectancy_r_gross"),
            "profit_factor_gross_total": summary.get("profit_factor_gross"),
            "fee_r_per_trade": summary.get("fee_r_per_trade"),
            "fee_total_r": summary.get("fee_total_r"),
            "pnl_r_total": summary.get("pnl_r"),
            "expectancy_r_total": summary.get("expectancy_r"),
            "profit_factor_total": summary.get("profit_factor"),
            # Long-Stats
            "n_long": long_stats["n"],
            "wins_long": long_stats["wins"],
            "losses_long": long_stats["losses"],
            "winrate_long": long_stats["winrate"],
            "pnl_r_gross_long": long_stats["pnl_r_gross"],
            "expectancy_r_gross_long": long_stats["expectancy_r_gross"],
            "profit_factor_gross_long": long_stats["profit_factor_gross"],
            "pnl_r_long": long_stats["pnl_r"],
            "expectancy_r_long": long_stats["expectancy_r"],
            "profit_factor_long": long_stats["profit_factor"],
            # Short-Stats
            "n_short": short_stats["n"],
            "wins_short": short_stats["wins"],
            "losses_short": short_stats["losses"],
            "winrate_short": short_stats["winrate"],
            "pnl_r_gross_short": short_stats["pnl_r_gross"],
            "expectancy_r_gross_short": short_stats["expectancy_r_gross"],
            "profit_factor_gross_short": short_stats["profit_factor_gross"],
            "pnl_r_short": short_stats["pnl_r"],
            "expectancy_r_short": short_stats["expectancy_r"],
            "profit_factor_short": short_stats["profit_factor"],
        }

        print(json.dumps(row, indent=2))
        rows.append(row)

    return rows


def save_results(rows: List[Dict[str, Any]]) -> None:
    """
    Speichert die Ergebnisliste als CSV und JSON.
    """
    _ensure_out_dir()

    # JSON
    OUT_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # CSV
    if not rows:
        print("Keine Daten zu speichern.")
        return

    fieldnames = list(rows[0].keys())
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nwritten: {OUT_CSV}")
    print(f"written: {OUT_JSON}")


def main() -> None:
    # Standard-Gitter:
    long_thresholds = [0.70, 0.75, 0.80]
    short_thresholds = [-0.55, -0.60, -0.65]

    rows = sweep_asym_thresholds(long_thresholds, short_thresholds)
    save_results(rows)


if __name__ == "__main__":
    main()
