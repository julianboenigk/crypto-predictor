# src/trade/paper.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

PAPER_FILE = Path("data/paper_trades.jsonl")
PAPER_FILE.parent.mkdir(parents=True, exist_ok=True)


def open_paper_trade(
    pair: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    size: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Legt einen virtuellen Trade an.
    Wird als JSON-Linie gespeichert, damit es einfach zu parsen ist.
    """
    rec = {
        "t": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "side": side,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "size": size,
        "status": "OPEN",
        "meta": meta or {},
    }
    with PAPER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
