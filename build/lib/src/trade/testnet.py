# src/trade/testnet.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

TESTNET_FILE = Path("data/testnet_trades.jsonl")
TESTNET_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_closed_testnet_trade(
    pair: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    size: float,
    exit_price: float,
    outcome: str,
    opened_at: Optional[str] = None,
    exit_time: Optional[str] = None,
    pnl_r: Optional[float] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Loggt einen abgeschlossenen Testnet-Trade.

    Achtung:
    - Aktuell spiegeln wir die Ergebnisse aus den Paper-Trades
      (pnl_r und outcome).
    - Später können wir hier echte Testnet-Execution-Daten verwenden.
    """
    if exit_time is None:
        exit_time = _now_iso()

    rec: Dict[str, Any] = {
        "pair": pair,
        "side": side.upper(),
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "size": float(size),
        "open_time": opened_at,
        "exit_time": exit_time,
        "exit": float(exit_price),
        "outcome": outcome.upper(),  # z.B. "TP", "SL", "MANUAL"
        "pnl_r": float(pnl_r) if pnl_r is not None else 0.0,
        "status": "CLOSED",
        "meta": meta or {},
    }

    with TESTNET_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    return rec


def iter_testnet_trades() -> Iterable[Dict[str, Any]]:
    """
    Liefert alle abgeschlossenen Testnet-Trades.
    """
    if not TESTNET_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with TESTNET_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    return _gen()
