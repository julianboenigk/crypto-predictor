# src/backtest/sweep_score_min.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Any

from src.backtest.run_latest import run_all
from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary

OUT_CSV = Path("data/reports/backtest_sweep_score_min.csv")
OUT_JSON = Path("data/reports/backtest_sweep_score_min.json")


def _ensure_out_dir() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)


def sweep_score_min(thresholds: Iterable[float]) -> List[Dict[str, Any]]:
    """
    Führt für jeden Wert in `thresholds` einen kompletten Backtest aus
    und sammelt die wichtigsten Kennzahlen (brutto & netto).
    """
    _ensure_out_dir()
    rows: List[Dict[str, Any]] = []

    for thr in thresholds:
        thr = float(thr)
        print(f"\n=== score_min = {thr:.2f} ===")

        # 1) Backtest ausführen
        run_all(score_min=thr)

        # 2) Neueste Backtest-Datei laden
        data = load_latest_backtest()

        # 3) PnL-Summary berechnen
        summary = compute_pnl_summary(data)

        row: Dict[str, Any] = {
            "score_min": thr,
            "file": summary.get("file"),
            "n_trades": summary.get("n_trades"),
            "wins": summary.get("wins"),
            "losses": summary.get("losses"),
            "winrate": summary.get("winrate"),
            "rr": summary.get("rr"),
            "pnl_r_gross": summary.get("pnl_r_gross"),
            "expectancy_r_gross": summary.get("expectancy_r_gross"),
            "profit_factor_gross": summary.get("profit_factor_gross"),
            "fee_r_per_trade": summary.get("fee_r_per_trade"),
            "fee_total_r": summary.get("fee_total_r"),
            "pnl_r": summary.get("pnl_r"),
            "expectancy_r": summary.get("expectancy_r"),
            "profit_factor": summary.get("profit_factor"),
        }

        # Kurz auf stdout anzeigen
        print(json.dumps(row, indent=2))

        rows.append(row)

    return rows


def save_results(rows: List[Dict[str, Any]]) -> None:
    """
    Speichert die Sweep-Ergebnisse als CSV und JSON.
    """
    _ensure_out_dir()

    # JSON
    OUT_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # CSV
    import csv

    fieldnames = [
        "score_min",
        "file",
        "n_trades",
        "wins",
        "losses",
        "winrate",
        "rr",
        "pnl_r_gross",
        "expectancy_r_gross",
        "profit_factor_gross",
        "fee_r_per_trade",
        "fee_total_r",
        "pnl_r",
        "expectancy_r",
        "profit_factor",
    ]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"\nwritten: {OUT_CSV}")
    print(f"written: {OUT_JSON}")


def main() -> None:
    # Standard-Sweep: 0.4, 0.5, 0.6, 0.7
    thresholds = [0.4, 0.5, 0.6, 0.7]
    rows = sweep_score_min(thresholds)
    save_results(rows)


if __name__ == "__main__":
    main()
