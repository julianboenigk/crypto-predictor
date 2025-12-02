from __future__ import annotations
import json
from src.backtest.run_latest import run_all
from src.reports.backtest_pnl_summary import load_latest_backtest


def main(score_min: float = 0.6) -> None:
    """
    Läuft die neue Backtest-Pipeline (run_all) und gibt danach
    das neueste Backtest-JSON kompakt auf stdout aus.
    """
    # 1) Neuen Backtest erzeugen
    run_all(score_min=score_min)

    # 2) Neueste Backtest-Datei finden und Kennzahlen anzeigen
    data = load_latest_backtest()
    print(f"data/backtests/{data['file']}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
