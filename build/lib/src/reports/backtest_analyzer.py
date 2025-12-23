# src/reports/backtest_analyzer.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List


BACKTEST_DIR = Path("data/backtests")


def load_all_backtests() -> List[Dict[str, Any]]:
    if not BACKTEST_DIR.exists():
        return []
    files = sorted(BACKTEST_DIR.glob("backtest_*.json"))
    out: List[Dict[str, Any]] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = f.name
            out.append(data)
        except Exception:
            continue
    return out


def summarize(bt: Dict[str, Any]) -> Dict[str, Any]:
    n_trades = int(bt.get("n_trades", 0))
    wins = int(bt.get("wins", 0))
    losses = int(bt.get("losses", 0))
    unknown = int(bt.get("unknown", 0))
    winrate = (wins / n_trades * 100.0) if n_trades > 0 else 0.0
    return {
        "file": bt.get("_file", ""),
        "n_trades": n_trades,
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "winrate_pct": round(winrate, 2),
    }


def main() -> None:
    all_bts = load_all_backtests()
    if not all_bts:
        print("no backtests found")
        return
    rows = [summarize(bt) for bt in all_bts]
    # simple table text
    print("file,n_trades,wins,losses,unknown,winrate_pct")
    for r in rows:
        print(
            f"{r['file']},{r['n_trades']},{r['wins']},{r['losses']},{r['unknown']},{r['winrate_pct']}"
        )


if __name__ == "__main__":
    main()
