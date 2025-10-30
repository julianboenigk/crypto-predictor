# src/fetchers/sentiment_refresh.py
# -----------------------------------------------------------------------------
# Pull daily sentiment per ticker from CryptoNews STAT endpoint and write to
# data/sentiment/{TICKER}.json. Prints:
#   [SENT-REFRESH] BTCUSDT pol=+0.15 vz=+0.00 sig=0.50 -> data/sentiment/BTCUSDT.json
#
# Notes:
# - The API reports scores in [-1.5, +1.5]. We normalize to [-1.0, +1.0] for 'pol'.
# - 'vz' is a simple volume/coverage proxy (articles counted vs 30d median), but
#   we keep it conservative to 0.00 if data is not present.
# - 'sig' is a static 0.50 until you choose a better confidence model.
#
# Requires: CRYPTONEWS_API_KEY (preferred) or CRYPTONEWS_API_KEY in .env
# Uses: src/providers/cryptonews.py (fetch_sentiment_ticker)
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

from src.providers.cryptonews import fetch_sentiment_ticker


def _ensure_dirs():
    Path("data/sentiment").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)


def _pair_to_ticker(pair: str) -> str:
    upper = pair.upper()
    for suf in ("USDT", "USD", "EUR", "USDC", "BUSD"):
        if upper.endswith(suf):
            return upper[: -len(suf)]
    return upper


def _extract_timeseries(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Try to pull the daily sentiment series from provider response.
    Common shapes:
      {"data":[{"date":"2025-10-30","overall_sentiment_score": 0.4, "articles": 23}, ...]}
    """
    data = payload.get("data")
    if isinstance(data, list):
        return data
    # some variants: {"stats": [...]} or {"data":{"items":[...]}}
    if isinstance(data, dict) and "items" in data:
        items = data.get("items", [])
        return items if isinstance(items, list) else []
    if "stats" in payload and isinstance(payload["stats"], list):
        return payload["stats"]
    return []


def _get_latest_sentiment(ts: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not ts:
        return None
    # assume last element is most recent if not sorted; sort defensively by date
    try:
        ts_sorted = sorted(
            ts,
            key=lambda x: str(x.get("date") or x.get("day") or x.get("ts") or ""),
        )
        return ts_sorted[-1]
    except Exception:
        return ts[-1]


def _normalize_score(v: float) -> float:
    """
    Provider range is typically [-1.5, +1.5]. Convert to [-1, +1].
    If value already within [-1, +1], keep as-is.
    """
    if abs(v) <= 1.5:
        v = v / 1.5
    return max(-1.0, min(1.0, v))


def _read_float(d: Dict[str, Any], keys: List[str]) -> float | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except Exception:
                continue
    return None


def run(pairs: List[str], date_window: str, page: int, cache: str | None):
    _ensure_dirs()
    load_dotenv(override=False)

    for pair in pairs:
        ticker = _pair_to_ticker(pair)
        try:
            raw = fetch_sentiment_ticker(
                ticker,
                date_window=date_window,
                page=page,
                cache=(None if cache is None else (cache.lower() == "true")),
            )
            series = _extract_timeseries(raw)

            latest = _get_latest_sentiment(series)
            if not latest:
                # fallback to neutral if no data
                pol = 0.0
                vz = 0.0
            else:
                # sentiment value (various field names tolerated)
                val = _read_float(
                    latest,
                    ["overall_sentiment_score", "sentiment_score", "score", "value"],
                )
                pol = _normalize_score(val) if (val is not None) else 0.0

                # crude "volume z" proxy: compare today's article count to 30d median
                # field names commonly 'articles', 'count', 'doc_count'
                count = _read_float(latest, ["articles", "count", "doc_count"]) or 0.0
                hist_counts = [
                    _read_float(d, ["articles", "count", "doc_count"]) or 0.0
                    for d in series[-30:]
                ]
                hist_counts = [c for c in hist_counts if c and c >= 0]
                if len(hist_counts) >= 5:
                    med = statistics.median(hist_counts)
                    vz = float((count - med) / (med if med > 0 else 1.0))
                    # keep it in a modest band like earlier logs
                    if vz > 1.0:
                        vz = 1.0
                    if vz < -1.0:
                        vz = -1.0
                else:
                    vz = 0.0

            out = {
                "pair": pair,
                "ticker": ticker,
                "date_window": date_window,
                "pol": round(pol, 2),  # [-1..+1]
                "vz": round(vz, 2),   # [-1..+1] proxy
                "sig": 0.50,          # keep fixed until you design a better model
                "raw_days": len(series),
            }

            out_path = Path(f"data/sentiment/{pair}.json")
            out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
            print(
                f"[SENT-REFRESH] {pair} pol={out['pol']:+.2f} vz={out['vz']:+.2f} "
                f"sig={out['sig']:.2f} -> {out_path}"
            )

        except Exception as e:
            print(f"[SENT-REFRESH][ERROR] {pair}: {e!r}")


def parse_args():
    p = argparse.ArgumentParser(description="Refresh CryptoNews STAT sentiment.")
    p.add_argument(
        "--pairs",
        nargs="*",
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"],
        help="Trading pairs (default: common top6).",
    )
    p.add_argument(
        "--date",
        dest="date_window",
        default="last1days",  # valid per provider docs
        help="Date window (today, yesterday, last7days, last30days, yeartodate, or ranges).",
    )
    p.add_argument("--page", type=int, default=1, help="Pagination page.")
    p.add_argument(
        "--cache",
        choices=["true", "false"],
        default=None,
        help="Override provider cache behavior.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.pairs, args.date_window, args.page, args.cache)
