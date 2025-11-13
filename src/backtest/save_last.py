# src/backtest/save_last.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.backtest.real import run_real_backtest

OUT_DIR = Path("data/backtests")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """
    Läuft den Real-Backtest über data/runs.log
    und schreibt ein Snapshot-JSON mit Zeitstempel.
    """
    res = run_real_backtest(
        path="data/runs.log",
        thr=0.4,          # gleich wie in deinen anderen Backtests
        lookahead_bars=24
    )
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = OUT_DIR / f"backtest_{ts}.json"
    out_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(str(out_file))


if __name__ == "__main__":
    main()
