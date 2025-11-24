# src/trade/live.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

LIVE_FILE = Path("data/live_trades.jsonl")
LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_live_dry_run_trade(
    pair: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    size: float = 1.0,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Schreibe einen simulierten Live-Trade (Dry-Run) in eine JSONL-Datei.

    Diese Funktion wird von src.app.main aufgerufen, wenn:
    - ENVIRONMENT == "live"
    - DRY_RUN == True
    - Score- und Risk-Gates erfüllt sind

    Es werden KEINE echten Orders an Binance gesendet.
    """
    rec: Dict[str, Any] = {
        "mode": "live_dry_run",
        "pair": pair,
        "side": side.upper(),
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "size": float(size),
        "opened_at": _now_iso(),
        "meta": meta or {},
    }

    with LIVE_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec))
        f.write("\n")


def iter_live_trades() -> Iterable[Dict[str, Any]]:
    """
    Liefert alle bisher geloggten Live-Dry-Run-Trades als Generator.
    Praktisch für Reports / Healthchecks.
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
                except json.JSONDecodeError:
                    continue

    return _gen()
