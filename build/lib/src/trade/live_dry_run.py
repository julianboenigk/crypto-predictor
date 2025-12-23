# src/trade/live_dry_run.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

LIVE_DRY_RUN_FILE = Path("data/live_trades_dry_run.jsonl")

LIVE_DRY_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_live_dry_run_trade(
    pair: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    score: float,
    reason: str,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Loggt einen "Live"-Trade im Dry-Run-Modus.

    Es werden KEINE Orders an Binance geschickt; das ist nur ein Log,
    der später wie paper_trades ausgewertet werden kann.
    """
    rec: Dict[str, Any] = {
        "t": _now_iso(),
        "env": "live-dry-run",
        "pair": pair,
        "side": side.upper(),
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "score": float(score),
        "reason": reason,
        "status": "OPEN",
        "meta": meta or {},
    }
    with LIVE_DRY_RUN_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def iter_live_dry_run_trades() -> Iterable[Dict[str, Any]]:
    """
    Hilfsfunktion, um alle bisher geloggten Live-Dry-Run-Trades zu lesen.
    Praktisch für spätere Reports.
    """
    if not LIVE_DRY_RUN_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with LIVE_DRY_RUN_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # defekten Eintrag überspringen
                    continue

    return _gen()
