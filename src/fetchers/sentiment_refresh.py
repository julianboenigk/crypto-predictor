# src/fetchers/sentiment_refresh.py
# Pulls CryptoNews sentiment STATs per symbol and writes normalized JSON
# with (polarity, velocity, signal). Uses provider retry/backoff.

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

# Best-effort .env loading (won’t crash if not present)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.providers.cryptonews import (
    fetch_sentiment_stat,
    parse_sentiment_from_stat,
)

# Provider-allowed windows
ALLOWED_WINDOWS = {
    "last5min", "last10min", "last15min", "last30min", "last45min", "last60min",
    "today", "yesterday", "last7days", "last30days", "last60days", "last90days",
    "yeartodate",
}

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def refresh_sentiment(
    symbols: List[str],
    date_window: str,
    out_dir: str,
    page: int = 1,
    cache: bool = False,
) -> None:
    _ensure_dir(out_dir)

    for sym in symbols:
        try:
            stat = fetch_sentiment_stat(sym, date_window=date_window, page=page, cache=cache)
            pol, vz, sig = parse_sentiment_from_stat(stat)
            payload = {
                "symbol": sym,
                "provider": "cryptonews/stat",
                "date_window": date_window,
                "polarity": round(float(pol), 4),
                "velocity": round(float(vz), 4),
                "signal": round(float(sig), 4),
                "raw": stat,  # keep raw for traceability
                "ts": _now_iso(),
            }
            out_path = os.path.join(out_dir, f"{sym}.json")
            _write_json(out_path, payload)
            print(f"[SENT-REFRESH] {sym} pol={pol:+.2f} vz={vz:+.2f} sig={sig:.2f} -> {out_path}")
        except Exception as e:
            print(f"[SENT-REFRESH][ERROR] {sym}: {repr(e)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Refresh CryptoNews sentiment stats and write normalized JSON."
    )
    p.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help=f"Comma-separated symbols, default={','.join(DEFAULT_SYMBOLS)}",
    )
    p.add_argument(
        "--date-window",
        type=str,
        default="yesterday",
        choices=sorted(ALLOWED_WINDOWS),
        help="Date window per provider docs (default: yesterday).",
    )
    p.add_argument(
        "--page",
        type=int,
        default=1,
        help="Page number for provider pagination (default: 1).",
    )
    p.add_argument(
        "--cache",
        type=lambda x: str(x).lower() in {"1", "true", "yes", "y"},
        default=False,
        help="Pass through provider cache=true|false (default: false).",
    )
    p.add_argument(
        "--outdir",
        type=str,
        default="data/sentiment",
        help="Output directory (default: data/sentiment).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    refresh_sentiment(
        symbols=symbols,
        date_window=args.date_window,
        out_dir=args.outdir,
        page=args.page,
        cache=args.cache,
    )


if __name__ == "__main__":
    main()
