# src/fetchers/news_refresh.py
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.providers.cryptonews import fetch_news_list

UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]

def _pair_to_ticker(pair: str) -> str:
    return pair.replace("USDT", "").upper()

def _extract_item_sentiment(item: Dict[str, Any]) -> float:
    """
    CryptoNews news items sometimes have a 'sentiment' or 'sentiment_score' field, sometimes not.
    Normalize to [-1..+1], fallback 0.0 if unknown.
    """
    s = item.get("sentiment")
    if s is None:
        s = item.get("sentiment_score")
    try:
        # Could be "-1","0","1","-0.3", etc.
        val = float(s)
        # clip to [-1..+1]
        return max(-1.0, min(1.0, val))
    except Exception:
        return 0.0

def _bias_and_novelty(items: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    bias = mean sentiment in [-1..+1] (0 if no items).
    novelty = fraction of unique sources in [0..1] (proxy).
    """
    if not items:
        return 0.0, 0.0
    sentiments = [_extract_item_sentiment(it) for it in items]
    bias = sum(sentiments) / max(1, len(sentiments))

    sources = [it.get("source_name") or it.get("source") or it.get("site") for it in items]
    uniq = len({s for s in sources if s})
    novelty = uniq / max(1, len(items))
    return bias, novelty

def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh CryptoNews article list and write per-ticker JSON.")
    parser.add_argument("--date", default="last60min", help="time window: last5min, last15min, last60min, today, yesterday, etc.")
    parser.add_argument("--items", type=int, default=50, help="max items")
    parser.add_argument("--cache", default="false", choices=["true", "false"], help="provider cache hint")
    parser.add_argument("--outdir", default="data/news", help="output directory")
    args = parser.parse_args()

    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    for pair in UNIVERSE:
        tkr = _pair_to_ticker(pair)
        try:
            items = fetch_news_list(tkr, date_window=args.date, items=args.items, cache=(args.cache == "true"))
            if not isinstance(items, list):
                # extremely defensive: normalize again
                items = items if isinstance(items, list) else []
            bias, novelty = _bias_and_novelty(items)
            payload = {
                "pair": pair,
                "ticker": tkr,
                "date_window": args.date,
                "items": items[: args.items],
                "bias": round(bias, 2),
                "novelty": round(novelty, 2),
                "source": "cryptonews/list",
            }
            outfile = outdir / f"{pair}.json"
            with open(outfile, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"[NEWS-REFRESH] {pair} bias={payload['bias']:+.2f} novelty={payload['novelty']:.2f} -> {outfile}")
        except Exception as e:
            print(f"[NEWS-REFRESH][ERROR] {pair}: {repr(e)}", file=sys.stderr)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
