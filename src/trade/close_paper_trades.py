# src/trade/close_paper_trades.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

# .env laden (u. a. für BINANCE_TESTNET_ENABLED)
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
from src.trade.testnet import (
    iter_testnet_trades,
    record_closed_testnet_trade,
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


def _make_key_paper_open(tr: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        tr.get("t"),
        tr.get("pair"),
        str(tr.get("side", "")).upper(),
        round(float(tr.get("entry", 0.0)), 8),
        round(float(tr.get("stop_loss", 0.0)), 8),
        round(float(tr.get("take_profit", 0.0)), 8),
        float(tr.get("size", 0.0)),
    )


def _make_key_paper_closed(tr: Dict[str, Any]) -> Tuple[Any, ...]:
    return (
        tr.get("open_time") or tr.get("t"),
        tr.get("pair"),
        str(tr.get("side", "")).upper(),
        round(float(tr.get("entry", 0.0)), 8),
        round(float(tr.get("stop_loss", 0.0)), 8),
        round(float(tr.get("take_profit", 0.0)), 8),
        float(tr.get("size", 0.0)),
    )


def _make_key_testnet(tr: Dict[str, Any]) -> Tuple[Any, ...]:
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


def _sync_testnet_from_closed_paper(
    closed_paper: List[Dict[str, Any]],
    existing_testnet: List[Dict[str, Any]],
    mirror_enabled: bool,
) -> int:
    """
    Spiegel bereits vorhandene abgeschlossene Paper-Trades in die
    Testnet-Trade-Datei, falls dort noch kein entsprechender Eintrag existiert.

    Aktuell nutzen wir dieselben Ergebnisse (pnl_r, outcome) – Ziel ist,
    eine identische Lifecycle-Logik zu haben. Später kann hier echte
    Testnet-Execution einfließen.
    """
    if not mirror_enabled:
        return 0

    paper_keys = { _make_key_paper_closed(tr) for tr in closed_paper }
    testnet_keys = { _make_key_testnet(tr) for tr in existing_testnet }

    missing_keys = paper_keys - testnet_keys
    if not missing_keys:
        return 0

    key_to_paper: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for tr in closed_paper:
        key = _make_key_paper_closed(tr)
        key_to_paper[key] = tr

    created = 0
    for key in missing_keys:
        tr = key_to_paper.get(key)
        if tr is None:
            continue

        entry = float(tr.get("entry"))
        sl = float(tr.get("stop_loss"))
        tp = float(tr.get("take_profit"))
        size = float(tr.get("size", 1.0))
        side = str(tr.get("side", "LONG")).upper()
        outcome = str(tr.get("outcome", "")).upper() or "MANUAL"
        exit_price = float(tr.get("exit", tp if outcome == "TP" else sl))
        pnl_r = float(tr.get("pnl_r", 0.0))
        opened_at = tr.get("open_time") or tr.get("t")
        exit_time = tr.get("exit_time")
        meta = tr.get("meta") or {}
        meta = {**meta, "source": "mirror_from_paper"}

        record_closed_testnet_trade(
            pair=str(tr.get("pair")),
            side=side,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            size=size,
            exit_price=exit_price,
            outcome=outcome,
            opened_at=opened_at,
            exit_time=exit_time,
            pnl_r=pnl_r,
            meta=meta,
        )
        created += 1

    return created


def main() -> None:
    # 0) Env-Flag, ob wir überhaupt Testnet-Trades spiegeln wollen
    testnet_mirror_enabled = os.getenv("BINANCE_TESTNET_ENABLED", "false").lower() == "true"

    # 1) Offene + bereits geschlossene Paper-Trades einlesen
    open_trades = list(iter_paper_trades())
    closed_trades = list(iter_closed_paper_trades())
    existing_testnet_trades = list(iter_testnet_trades())

    # 1a) Bereits geschlossene Paper-Trades nach Testnet spiegeln (Backfill)
    testnet_backfill = _sync_testnet_from_closed_paper(
        closed_paper=closed_trades,
        existing_testnet=existing_testnet_trades,
        mirror_enabled=testnet_mirror_enabled,
    )

    closed_keys = { _make_key_paper_closed(tr) for tr in closed_trades }
    candidates: List[Dict[str, Any]] = []

    for tr in open_trades:
        key = _make_key_paper_open(tr)
        if key in closed_keys:
            # bereits verarbeitet
            continue
        candidates.append(tr)

    # 2) Pro Kandidat prüfen, ob SL/TP inzwischen getroffen wurde
    if not candidates:
        summary = {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "open_seen": len(open_trades),
            "closed_existing": len(closed_trades),
            "closed_new": 0,
            "testnet_backfill": testnet_backfill,
            "errors": [],
        }
        print(json.dumps(summary, indent=2))
        return

    # grob nach (pair, interval) gruppieren
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for tr in candidates:
        pair = str(tr.get("pair"))
        interval = str(tr.get("interval") or "15m")
        key = (pair, interval)
        groups.setdefault(key, []).append(tr)

    closed_new = 0
    testnet_new = 0
    errors: List[str] = []

    for (pair, interval), trs in groups.items():
        # Binance-Limit: max 1000 Kerzen; reicht für ca. 10 Tage bei 15m
        lookback = 1000

        try:
            klines = get_ohlcv(pair, interval, limit=lookback)
        except Exception as e:
            errors.append(f"get_ohlcv failed for {pair} {interval}: {e}")
            continue

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

            klines_tr = _filter_klines_since(klines, opened_at)
            if not klines_tr:
                continue

            outcome = _simulate_over_klines(side, sl, tp, klines_tr)
            if outcome not in ("TP", "SL"):
                # noch nicht getroffen -> Trade bleibt offen
                continue

            exit_price = tp if outcome == "TP" else sl

            # Paper-Trade als geschlossen loggen (berechnet intern pnl_r)
            paper_rec = record_closed_paper_trade(
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

            # Testnet-Trade spiegeln (optional, abhängig vom Env-Flag)
            if testnet_mirror_enabled:
                meta_testnet = {**(paper_rec.get("meta") or {}), "source": "mirror_from_paper"}
                record_closed_testnet_trade(
                    pair=paper_rec["pair"],
                    side=paper_rec["side"],
                    entry=paper_rec["entry"],
                    stop_loss=paper_rec["stop_loss"],
                    take_profit=paper_rec["take_profit"],
                    size=paper_rec["size"],
                    exit_price=paper_rec["exit"],
                    outcome=paper_rec["outcome"],
                    opened_at=paper_rec.get("open_time"),
                    exit_time=paper_rec.get("exit_time"),
                    pnl_r=paper_rec.get("pnl_r", 0.0),
                    meta=meta_testnet,
                )
                testnet_new += 1

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "open_seen": len(open_trades),
        "closed_existing": len(closed_trades),
        "closed_new": closed_new,
        "testnet_backfill": testnet_backfill,
        "testnet_new": testnet_new,
        "errors": errors,
    }
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
