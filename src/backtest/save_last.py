# src/backtest/save_last.py

from __future__ import annotations

import json
from typing import Optional

from src.backtest.run_latest import run_all
from src.app.main import FINAL_SCORE_MIN
from src.reports.backtest_pnl_summary import (
    load_latest_backtest,
    compute_pnl_summary,
)


def main(score_min: Optional[float] = None) -> None:
    """
    Läuft die neue Backtest-Pipeline (run_all) und gibt danach
    die PnL-Zusammenfassung des neuesten Backtests auf stdout aus.

    score_min:
        - Wenn None: FINAL_SCORE_MIN aus src.app.main
        - Sonst: explizit übergebener Score-Gate-Wert
    """
    if score_min is None:
        score_min = FINAL_SCORE_MIN

    # 1) Neuen Backtest erzeugen
    run_all(score_min=float(score_min))

    # 2) Neueste Backtest-Datei laden (Rohdaten)
    bt_data = load_latest_backtest()

    # 3) PnL-Summary berechnen (inkl. "file"-Feld)
    summary = compute_pnl_summary(bt_data)

    fname = summary.get("file", "unknown")
    print(f"data/backtests/{fname}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()