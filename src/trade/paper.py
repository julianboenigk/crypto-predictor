# src/trade/paper.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

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
    Schreibe einen virtuellen Trade (Paper Trade) in eine JSONL-Datei.

    Diese Funktion wird von src.app.main aufgerufen, sobald ein Signal
    stark genug ist und PAPER_ENABLED=True ist.

    Wir loggen nur den "OPEN"-Zeitpunkt. Auswertung / Schließen der Trades
    kann später separat implementiert werden.
    """
    rec: Dict[str, Any] = {
        "t": datetime.now(timezone.utc).isoformat(),
        "pair": pair,
        "side": side.upper(),
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "size": float(size),
        "status": "OPEN",
        "meta": meta or {},
    }
    with PAPER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def iter_paper_trades() -> Iterable[Dict[str, Any]]:
    """
    Hilfsfunktion, um alle bisher geloggten Paper-Trades zu lesen.
    Wird aktuell noch nicht von main verwendet, ist aber nützlich
    für spätere Reports / Auswertungen.
    """
    if not PAPER_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with PAPER_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # defekten Eintrag überspringen, Log bleibt robust
                    continue

    return _gen()
