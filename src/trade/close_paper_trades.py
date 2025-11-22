# src/trade/close_paper_trades.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# .env laden (u. a. für BINANCE_* Settings)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

from src.trade.paper import (
    iter_paper_trades,
    iter_closed_paper_trades,
    record_closed_paper_trade,
)
from src.data.binance_client import get_ohlcv  # type: ignore


DATA_DIR = Path("data")


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    s = str(raw)
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def _make_key_open(tr: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        tr.get("t"),
        tr.get("pair"),
        str(tr.get("side", "")).upper(),
        round(float(tr.get("entry", 0.0)), 8),
        round(float(tr.get("stop_loss", 0.0)), 8),
        round(float(tr.get("take_profit", 0.0)), 8),
        float(tr.get("size", 0.0)),
    )


def _make_key_closed(tr: Dict[str, Any]) -> Tuple[Any, ...]:
    # closed-trades haben "open_time" statt "t"
    return (
        tr.get("open_time"),
        tr.get("pair"),
        str(tr.get("side", "")).upper(),
        round(float(tr.get("entry", 0.0)), 8),
        round(float(tr.get("stop_loss", 0.0)), 8),
        round(float(tr.get("take_profit", 0.0)), 8),
        float(tr.get("size", 0.0)),
    )


def _simulate_over_klines(
    side: str,
    sl: float,
    tp: float,
    klines: List[List[Any]],
) -> str:
    """
    Simuliere einen Trade über eine Liste von Binance-Kerzen.
    Jede Kline: [open_time, open, high, low, close, volume, ...]
    """
    side_u = str(side).upper()
    for k in klines:
        high = float(k[2])
        low = float(k[3])
        if side_u == "LONG":
            if high >= tp:
                return "TP"
            if low <= sl:
                return "SL"
        else:  # SHORT
            if low <= tp:
                return "TP"
            if high >= sl:
                return "SL"
    return "UNKNOWN"


def _filter_klines_since(
    klines: List[List[Any]],
    opened_at: datetime,
) -> List[List[Any]]:
    """
    Filtert die OHLCV-Kerzen, so dass nur Kerzen nach dem Entry
    betrachtet werden. open_time ist im ms-Format in k[0].
    """
    out: List[List[Any]] = []
    cutoff_ms = int(opened_at.timestamp() * 1000)
    for k in klines:
        open_time_ms = int(k[0])
        if open_time_ms >= cutoff_ms:
            out.append(k)
    return out


def main() -> None:
    # 1) Offene + bereits geschlossene Trades einlesen
    open_trades = list(iter_paper_trades())
    closed_trades = list(iter_closed_paper_trades())

    closed_keys = { _make_key_closed(tr) for tr in closed_trades }
    candidates: List[Dict[str, Any]] = []

    for tr in open_trades:
        key = _make_key_open(tr)
        if key in closed_keys:
            # bereits verarbeitet
            continue
        candidates.append(tr)

    if not candidates:
        print(json.dumps({"closed_new": 0, "msg": "no new candidates"}, indent=2))
        return

    # 2) Grob nach (pair, interval) gruppieren
    # Interval existiert aktuell nicht im Log -> wir nehmen "15m" als Default
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for tr in candidates:
        pair = str(tr.get("pair"))
        interval = str(tr.get("interval") or "15m")
        key = (pair, interval)
        groups.setdefault(key, []).append(tr)

    closed_new = 0
    errors: List[str] = []

    # 3) Pro Gruppe einmal OHLCV holen und dann alle Trades simulieren
    for (pair, interval), trs in groups.items():
        # Binance-Limit: max 1000 Kerzen; reicht für ca. 10 Tage bei 15m
        lookback = 1000

        klines = get_ohlcv(pair, interval, limit=lookback)
        if not klines:
            errors.append(f"no klines for {pair} {interval}")
            continue

        for tr in trs:
            opened_at = _parse_ts(tr.get("t"))
            if opened_at is None:
                continue

            sl = float(tr.get("stop_loss"))
            tp = float(tr.get("take_profit"))
            entry = float(tr.get("entry"))
            size = float(tr.get("size", 1.0))
            side = str(tr.get("side", "LONG")).upper()
            meta = tr.get("meta") or {}

            # nur Kerzen ab Entry berücksichtigen
            klines_tr = _filter_klines_since(klines, opened_at)
            if not klines_tr:
                continue

            outcome = _simulate_over_klines(side, sl, tp, klines_tr)
            if outcome not in ("TP", "SL"):
                # noch nicht getroffen -> Trade bleibt offen
                continue

            # Annahme: Exit-Preis entspricht getroffenen Level
            exit_price = tp if outcome == "TP" else sl

            rec = record_closed_paper_trade(
                pair=pair,
                side=side,
                entry=entry,
                stop_loss=sl,
                take_profit=tp,
                size=size,
                exit_price=exit_price,
                outcome=outcome,
                opened_at=tr.get("t"),
                meta=meta,
            )
            closed_new += 1

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "open_seen": len(open_trades),
        "closed_existing": len(closed_trades),
        "closed_new": closed_new,
        "errors": errors,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
