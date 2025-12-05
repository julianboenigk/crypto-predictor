from __future__ import annotations
import json
from src.backtest.run_latest import run_all
from src.reports.backtest_pnl_summary import load_latest_backtest, compute_pnl_summary


def main(score_min: float = 0.6) -> None:
    """
    Läuft die neue Backtest-Pipeline (run_all) und gibt danach
    die Kennzahlen des neuesten Backtests kompakt auf stdout aus.
    """
    # 1) Neuen Backtest erzeugen
    run_all(score_min=score_min)

    # 2) Neueste Backtest-Datei laden und zusammenfassen
    raw = load_latest_backtest()           # rohes Backtest-JSON (mit "_file")
    summary = compute_pnl_summary(raw)     # aggregierte Kennzahlen

    fname = raw.get("_file", "unknown")
    print(f"data/backtests/{fname}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()