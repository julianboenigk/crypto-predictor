# src/backtest/loader.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List


def load_runs(path: str = "data/runs.log") -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                out.append(obj)
            except Exception:
                continue
    return out


def to_signals(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sigs: List[Dict[str, Any]] = []
    for run in runs:
        t = run.get("run_at") or run.get("t")
        for res in run.get("results", []):
            sigs.append(
                {
                    "t": t,
                    "pair": res.get("pair"),
                    "score": float(res.get("score", 0.0)),
                    "decision": res.get("decision"),
                    "reason": res.get("reason"),
                    "breakdown": res.get("breakdown", []),
                    "interval": res.get("interval"),
                }
            )
    return sigs
