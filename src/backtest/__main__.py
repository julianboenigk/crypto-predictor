# src/backtest/__main__.py
from __future__ import annotations
import sys
import json

from src.backtest.real import run_real_backtest
from src.backtest.equity import build_equity_curve
from src.backtest.agent_stats import agent_contributions
from src.backtest.param_sweep import sweep_thresholds


def main() -> None:
    if len(sys.argv) == 1:
        print("Usage: python3 -m src.backtest [real|equity|agents|params]")
        return

    cmd = sys.argv[1].lower()

    if cmd == "real":
        res = run_real_backtest(path="data/runs.log", thr=0.4, lookahead_bars=24)
        print(json.dumps(res, indent=2))
    elif cmd == "equity":
        res = run_real_backtest(path="data/runs.log", thr=0.4, lookahead_bars=24)
        curve = build_equity_curve(res)
        print(json.dumps(curve, indent=2))
    elif cmd == "agents":
        res = agent_contributions("data/runs.log", thr=0.4)
        print(json.dumps(res, indent=2))
    elif cmd == "params":
        res = sweep_thresholds("data/runs.log")
        print(json.dumps(res, indent=2))
    else:
        print("unknown command")


if __name__ == "__main__":
    main()
