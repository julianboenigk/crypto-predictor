from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root is importable when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

from src.core.version import SYSTEM_VERSION

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
    interval_sec: int,
) -> List[List[Any]]:
    """
    Include the entry candle (critical for TP/SL detection).
    """
    cutoff_ms = int((opened_at.timestamp() - interval_sec) * 1000)
    out: List[List[Any]] = []
    for k in klines:
        if int(k[0]) >= cutoff_ms:
            out.append(k)
    return out


def _sync_testnet_from_closed_paper(
    closed_paper: List[Dict[str, Any]],
    existing_testnet: List[Dict[str, Any]],
    mirror_enabled: bool,
) -> int:
    if not mirror_enabled:
        return 0

    paper_keys = {_make_key_paper_closed(tr) for tr in closed_paper}
    testnet_keys = {_make_key_testnet(tr) for tr in existing_testnet}

    missing_keys = paper_keys - testnet_keys
    if not missing_keys:
        return 0

    key_to_paper = {_make_key_paper_closed(tr): tr for tr in closed_paper}
    created = 0

    for key in missing_keys:
        tr = key_to_paper.get(key)
        if tr is None:
            continue

        record_closed_testnet_trade(
            pair=str(tr.get("pair")),
            side=str(tr.get("side", "LONG")).upper(),
            entry=float(tr["entry"]),
            stop_loss=float(tr["stop_loss"]),
            take_profit=float(tr["take_profit"]),
            size=float(tr.get("size", 1.0)),
            exit_price=float(tr["exit"]),
            outcome=str(tr.get("outcome", "MANUAL")).upper(),
            opened_at=tr.get("open_time") or tr.get("t"),
            exit_time=tr.get("exit_time"),
            pnl_r=float(tr.get("pnl_r", 0.0)),
            meta={**(tr.get("meta") or {}), "source": "mirror_from_paper"},
        )
        created += 1

    return created


def main() -> None:
    testnet_mirror_enabled = os.getenv("BINANCE_TESTNET_ENABLED", "false").lower() == "true"

    open_trades = list(iter_paper_trades())
    closed_trades = list(iter_closed_paper_trades())
    existing_testnet_trades = list(iter_testnet_trades())

    testnet_backfill = _sync_testnet_from_closed_paper(
        closed_paper=closed_trades,
        existing_testnet=existing_testnet_trades,
        mirror_enabled=testnet_mirror_enabled,
    )

    closed_keys = {_make_key_paper_closed(tr) for tr in closed_trades}
    candidates = [tr for tr in open_trades if _make_key_paper_open(tr) not in closed_keys]

    if not candidates:
        print(json.dumps({
            "run_at": datetime.now(timezone.utc).isoformat(),
            "system_version": SYSTEM_VERSION,
            "open_seen": len(open_trades),
            "closed_existing": len(closed_trades),
            "closed_new": 0,
            "testnet_backfill": testnet_backfill,
            "errors": [],
        }, indent=2))
        return

    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for tr in candidates:
        groups.setdefault((str(tr.get("pair")), str(tr.get("interval") or "15m")), []).append(tr)

    closed_new = 0
    testnet_new = 0
    errors: List[str] = []

    for (pair, interval), trs in groups.items():
        interval_sec = {
            "1m": 60, "3m": 180, "5m": 300, "15m": 900,
            "30m": 1800, "1h": 3600, "2h": 7200,
            "4h": 14400, "1d": 86400,
        }.get(interval, 900)

        opened_times: List[datetime] = []
        for tr in trs:
            ts = _parse_ts(tr.get("t"))
            if ts is not None:
                opened_times.append(ts)
        if not opened_times:
            continue

        oldest_open = min(opened_times)
        seconds = max(0.0, (datetime.now(timezone.utc) - oldest_open).total_seconds())
        lookback = min(max(int(seconds // interval_sec) + 5, 100), 1000)

        try:
            klines_raw = get_ohlcv(pair, interval, limit=lookback)
        except Exception as e:
            errors.append(f"get_ohlcv failed for {pair} {interval}: {e}")
            continue

        if klines_raw is None:
            errors.append(f"no klines for {pair} {interval}")
            continue
        if not isinstance(klines_raw, list):
            errors.append(f"unexpected klines format for {pair} {interval}")
            continue
        if not klines_raw:
            errors.append(f"no klines for {pair} {interval}")
            continue

        klines: List[List[Any]] = klines_raw

        for tr in trs:
            opened_at = _parse_ts(tr.get("t"))
            if opened_at is None:
                continue

            klines_tr = _filter_klines_since(klines, opened_at, interval_sec)
            if not klines_tr:
                continue

            outcome = _simulate_over_klines(
                str(tr.get("side", "LONG")),
                float(tr["stop_loss"]),
                float(tr["take_profit"]),
                klines_tr,
            )

            if outcome not in ("TP", "SL"):
                continue

            paper_rec = record_closed_paper_trade(
                pair=pair,
                side=str(tr.get("side", "LONG")).upper(),
                entry=float(tr["entry"]),
                stop_loss=float(tr["stop_loss"]),
                take_profit=float(tr["take_profit"]),
                size=float(tr.get("size", 1.0)),
                exit_price=float(tr["take_profit"] if outcome == "TP" else tr["stop_loss"]),
                outcome=outcome,
                opened_at=tr.get("t"),
                meta=tr.get("meta") or {},
            )
            closed_new += 1

            if testnet_mirror_enabled:
                record_closed_testnet_trade(
                    pair=str(paper_rec["pair"]),
                    side=str(paper_rec.get("side", "LONG")).upper(),
                    entry=float(paper_rec["entry"]),
                    stop_loss=float(paper_rec["stop_loss"]),
                    take_profit=float(paper_rec["take_profit"]),
                    size=float(paper_rec.get("size", 1.0)),
                    exit_price=float(paper_rec["exit"]),
                    outcome=str(paper_rec.get("outcome", "MANUAL")).upper(),
                    opened_at=paper_rec.get("open_time"),
                    exit_time=paper_rec.get("exit_time"),
                    pnl_r=float(paper_rec.get("pnl_r", 0.0)),
                    meta={**(paper_rec.get("meta") or {}), "source": "mirror_from_paper"},
                )
                testnet_new += 1

    print(json.dumps({
        "run_at": datetime.now(timezone.utc).isoformat(),
        "system_version": SYSTEM_VERSION,
        "open_seen": len(open_trades),
        "closed_existing": len(closed_trades),
        "closed_new": closed_new,
        "testnet_backfill": testnet_backfill,
        "testnet_new": testnet_new,
        "errors": errors,
    }, indent=2))


if __name__ == "__main__":
    main()
