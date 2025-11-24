# src/trade/live.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

# Wir verwenden bewusst dieselbe Datei wie für den Live-Dry-Run-Logger,
# damit es keinen Namens-Mischmasch gibt.
LIVE_FILE: Path = Path("data/live_trades_dry_run.jsonl")


def iter_live_trades() -> Iterable[Dict[str, Any]]:
    """
    Liefert alle (Dry-Run-)Live-Trades aus data/live_trades_dry_run.jsonl
    als Generator von Dicts.
    """
    if not LIVE_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with LIVE_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    # Kaputte Zeilen überspringen, nicht crashen
                    continue

    return _gen()
