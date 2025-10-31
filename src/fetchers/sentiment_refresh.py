# src/fetchers/sentiment_refresh.py
# -*- coding: utf-8 -*-
"""
Fetches daily sentiment data for multiple crypto tickers from CryptoNews API
and stores normalized outputs in data/sentiment/<PAIR>.json

Uses:
  - src/providers/cryptonews.fetch_sentiment_stat()
  - src/providers/cryptonews.parse_sentiment_from_stat()

Example:
  python -m src.fetchers.sentiment_refresh --date yesterday --cache true
"""

import json
import time
import argparse
import pathlib
from typing import List

from src.providers.cryptonews import fetch_sentiment_stat, parse_sentiment_from_stat

# ---------- Configuration ----------
SYMBOLS: List[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
OUTDIR = pathlib.Path("data/sentiment")
OUTDIR.mkdir(parents=True, exist_ok=True)


# ---------- Helpers ----------
def _base_symbol(pair: str) -> str:
    """Convert trading pair to base ticker, e.g. BTCUSDT -> BTC"""
    return pair[:-4] if pair.endswith("USDT") else pair


# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Refresh CryptoNews sentiment data")
    parser.add_argument(
        "--date",
        default="yesterday",
        help="CryptoNews STAT date window (today, yesterday, last7days, last30days, etc.)",
    )
    parser.add_argument(
        "--cache",
        default="true",
        choices=["true", "false"],
        help="Use on-disk cache (true) or force fresh API calls (false)",
    )
    parser.add_argument(
        "--sleep_ms",
        type=int,
        default=300,
        help="Delay between API calls (ms) to avoid rate limits",
    )
    args = parser.parse_args()

    date_window = args.date
    use_cache = args.cache.lower() == "true"
    delay = max(0, args.sleep_ms) / 1000.0

    for sym in SYMBOLS:
        tkr = _base_symbol(sym)
        try:
            payload = fetch_sentiment_stat(tkr, date_window=date_window, cache=use_cache)
            parsed = parse_sentiment_from_stat(payload, tkr)

            pol = float(parsed.get("score", 0.0))           # polarity
            vz = 0.0                                        # velocity placeholder
            sig = round((pol + 1.0) / 2.0, 2)               # signal in [0,1]

            out = {
                "symbol": sym,
                "ticker": tkr,
                "date_window": date_window,
                "pol": pol,
                "vz": vz,
                "sig": sig,
                "counts": {
                    k: int(v)
                    for k, v in {
                        "positive": parsed.get("positive"),
                        "negative": parsed.get("negative"),
                        "neutral": parsed.get("neutral"),
                    }.items()
                    if v is not None
                },
                "source": parsed.get("source"),
                "ts": int(time.time()),
            }

            out_path = OUTDIR / f"{sym}.json"
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(out, f, indent=2, sort_keys=True)

            print(f"[SENT-REFRESH] {sym} pol={pol:+.2f} vz={vz:+.2f} sig={sig:.2f} -> {out_path}")
        except Exception as e:
            print(f"[SENT-REFRESH][ERROR] {sym}: {e}")

        if delay:
            time.sleep(delay)


if __name__ == "__main__":
    main()
