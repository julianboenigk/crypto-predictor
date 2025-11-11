# src/backtest/param_sweep.py
from __future__ import annotations
from typing import List, Dict, Any
from src.backtest.loader import load_runs, to_signals
from src.backtest.rule_based import backtest_signals


def sweep_thresholds(
    path: str = "data/runs.log",
    thresholds: List[float] = None,
) -> List[Dict[str, Any]]:
    if thresholds is None:
        thresholds = [0.4, 0.5, 0.6, 0.65, 0.7]
    runs = load_runs(path)
    sigs = to_signals(runs)
    out: List[Dict[str, Any]] = []
    for thr in thresholds:
        res = backtest_signals(
            sigs,
            long_thr=thr,
            short_thr=-thr,
            rr=1.5,
            winrate_assumption=0.55,
        )
        res["threshold"] = thr
        out.append(res)
    return out
