# src/trade/paper.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

PAPER_OPEN_FILE = Path("data/paper_trades.jsonl")          # historische OPEN-Logs (wie bisher)
PAPER_CLOSED_FILE = Path("data/paper_trades_closed.jsonl") # neue Datei für abgeschlossene Trades

PAPER_OPEN_FILE.parent.mkdir(parents=True, exist_ok=True)
PAPER_CLOSED_FILE.parent.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------
# OPEN Trade: unverändert, nur minimal aufgeräumt
# ------------------------------------------------------------

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
    erfolgt über separate Funktionen in diesem Modul.
    """
    rec: Dict[str, Any] = {
        "t": _now_iso(),
        "pair": pair,
        "side": side.upper(),
        "entry": float(entry),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "size": float(size),
        "status": "OPEN",
        "meta": meta or {},
    }
    with PAPER_OPEN_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def iter_paper_trades() -> Iterable[Dict[str, Any]]:
    """
    Hilfsfunktion, um alle bisher geloggten OPEN-Paper-Trades zu lesen.
    Wird aktuell noch nicht von main verwendet, ist aber nützlich
    für spätere Reports / Auswertungen.
    """
    if not PAPER_OPEN_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with PAPER_OPEN_FILE.open("r", encoding="utf-8") as f:
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


# ------------------------------------------------------------
# CLOSED Trades: neue Funktionen für echte Performance
# ------------------------------------------------------------

def _compute_pnl_r(
    side: str,
    entry: float,
    stop_loss: float,
    exit_price: float,
) -> float:
    """
    Berechnet R (Risk-Multiple) für einen abgeschlossenen Trade.

    R = (Exit - Entry) / (Entry - StopLoss)  für LONG
    R = (Entry - Exit) / (StopLoss - Entry)  für SHORT

    Wenn die Distanz Entry-StopLoss <= 0 ist, liefern wir 0.0 (defensiv).
    """
    side_u = side.upper()
    risk_per_unit: float

    if side_u == "LONG":
        risk_per_unit = entry - stop_loss
        if risk_per_unit <= 0:
            return 0.0
        return (exit_price - entry) / risk_per_unit

    elif side_u == "SHORT":
        risk_per_unit = stop_loss - entry
        if risk_per_unit <= 0:
            return 0.0
        return (entry - exit_price) / risk_per_unit

    # unbekannte Richtung -> konservativ
    return 0.0


def record_closed_paper_trade(
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
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Loggt einen abgeschlossenen Paper-Trade in PAPER_CLOSED_FILE.

    Dieser Eintrag ist die Grundlage für echte Performance-Auswertungen
    (z. B. daily_live_summary).
    """
    if exit_time is None:
        exit_time = _now_iso()

    pnl_r = _compute_pnl_r(side=side, entry=entry, stop_loss=stop_loss, exit_price=exit_price)

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
        "pnl_r": float(pnl_r),
        "status": "CLOSED",
        "meta": meta or {},
    }

    with PAPER_CLOSED_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")

    return rec


def iter_closed_paper_trades() -> Iterable[Dict[str, Any]]:
    """
    Liefert alle abgeschlossenen Paper-Trades aus PAPER_CLOSED_FILE.
    """
    if not PAPER_CLOSED_FILE.exists():
        return []

    def _gen() -> Iterable[Dict[str, Any]]:
        with PAPER_CLOSED_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    return _gen()
