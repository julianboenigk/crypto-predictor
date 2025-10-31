# src/fetchers/sentiment_refresh.py
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict

from src.providers.cryptonews import fetch_sentiment_stat, parse_sentiment_from_stat

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]

def _pair_to_ticker(pair: str) -> str:
    # Map "BTCUSDT" -> "BTC" for CryptoNews tickers
    return pair.replace("USDT", "").upper()

def _to_signal(score: float) -> float:
    # map score [-1..+1] into [0..1] with 0.5 neutral
    return max(0.0, min(1.0, 0.5 + score * 0.5))

def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh CryptoNews sentiment STAT and write per-ticker JSON.")
    parser.add_argument("--date", default="yesterday", help="time window: today, yesterday, last7days, last30days, etc.")
    parser.add_argument("--cache", default="false", choices=["true", "false"], help="provider cache hint")
    parser.add_argument("--outdir", default="data/sentiment", help="output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    for pair in UNIVERSE:
        tkr = _pair_to_ticker(pair)
        try:
            stat = fetch_sentiment_stat(tkr, date_window=args.date, cache=(args.cache == "true"))
            pol = float(stat.get("score", 0.0))
            # velocity not provided by STAT; keep 0.0 for now
            vz = 0.0
            sig = _to_signal(pol)
            payload = {"pair": pair, "ticker": tkr, "pol": round(pol, 2), "vz": round(vz, 2), "sig": round(sig, 2)}
            outfile = outdir / f"{pair}.json"
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[SENT-REFRESH] {pair} pol={payload['pol']:+.2f} vz={payload['vz']:+.2f} sig={payload['sig']:.2f} -> {outfile}")
        except Exception as e:
            print(f"[SENT-REFRESH][ERROR] {pair}: {repr(e)}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
