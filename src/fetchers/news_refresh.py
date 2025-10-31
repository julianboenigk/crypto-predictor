# src/fetchers/news_refresh.py
# -----------------------------------------------------------------------------
# Pull recent news for each pair from CryptoNews API and write compact summaries
# to data/news/{TICKER}.json. Prints one status line per pair:
#   [NEWS-REFRESH] BTCUSDT bias=+0.20 novelty=0.12 -> data/news/BTCUSDT.json
#
# Requires: CRYPTONEWS_API_KEY (preferred) or CRYPTONEWS_API_KEY in .env
# Uses: src/providers/cryptonews.py (fetch_news_ticker)
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Any

from dotenv import load_dotenv

# Local provider client
from src.providers.cryptonews import fetch_news_list as fetch_news_ticker

# -------------------------- helpers ------------------------------------------

def _ensure_dirs():
    Path("data/news").mkdir(parents=True, exist_ok=True)
    Path("data/logs").mkdir(parents=True, exist_ok=True)


def _pair_to_ticker(pair: str) -> str:
    # Convert "BTCUSDT" -> "BTC" (strip stablecoin suffixes)
    upper = pair.upper()
    for suf in ("USDT", "USD", "EUR", "USDC", "BUSD"):
        if upper.endswith(suf):
            return upper[: -len(suf)]
    return upper


def _extract_article_sentiment(a: Dict[str, Any]) -> float | None:
    """
    Try to read a numerical sentiment from article payload if present.
    CryptoNews may provide fields like 'sentiment', 'sentiment_score', etc.
    If none found, return None.
    """
    for k in ("sentiment_score", "sentiment", "score"):
        v = a.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        # some APIs use strings like "positive"/"negative"/"neutral"
        if isinstance(v, str):
            low = v.lower()
            if low in ("pos", "positive"):  # map to +1
                return 1.0
            if low in ("neg", "negative"):
                return -1.0
            if low in ("neu", "neutral"):
                return 0.0
    return None


def _compute_bias(articles: List[Dict[str, Any]]) -> float:
    """
    Average normalized sentiment across recent articles if available,
    else 0.0. Clamp to [-1.0, +1.0].
    """
    vals: List[float] = []
    for a in articles:
        s = _extract_article_sentiment(a)
        if s is not None:
            # CryptoNews STAT uses [-1.5, +1.5]; normalize to [-1, +1]
            if abs(s) <= 1.5:
                s = s / 1.5
            # otherwise assume already within [-1, +1]
            vals.append(max(-1.0, min(1.0, s)))
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return max(-1.0, min(1.0, m))


def _compute_novelty(articles: List[Dict[str, Any]]) -> float:
    """
    Crude novelty: unique sources / total * 0.5, capped at 0.5 (to mirror your logs).
    If nothing to go on, return 0.0.
    """
    if not articles:
        return 0.0
    sources = [a.get("source_name") or a.get("source") or "" for a in articles]
    uniq = len(set(s for s in sources if s))
    frac = (uniq / max(1, len(articles))) * 0.5
    return max(0.0, min(0.5, frac))


def _trim_article(a: Dict[str, Any]) -> Dict[str, Any]:
    """Keep a compact subset to avoid storing large payloads."""
    return {
        "title": a.get("title"),
        "source": a.get("source_name") or a.get("source"),
        "published_at": a.get("published_at") or a.get("date"),
        "url": a.get("news_url") or a.get("url"),
        "sent": _extract_article_sentiment(a),
    }


# --------------------------- main --------------------------------------------

def run(pairs: List[str], items: int, date_window: str, page: int, cache: str | None):
    _ensure_dirs()
    load_dotenv(override=False)

    for pair in pairs:
        ticker = _pair_to_ticker(pair)
        try:
            raw = fetch_news_ticker(
                ticker,
                items=items,
                date_window=date_window,
                page=page,
                cache=(None if cache is None else (cache.lower() == "true")),
            )
            # The provider commonly returns: {"data": [...]} or {"data": {"items": [...]}}
            data = raw.get("data")
            if isinstance(data, dict) and "items" in data:
                articles = data.get("items", [])
            elif isinstance(data, list):
                articles = data
            else:
                # Some variants use 'news' or 'items' at root
                articles = raw.get("items") or raw.get("news") or []

            if not isinstance(articles, list):
                articles = []

            bias = _compute_bias(articles)
            novelty = _compute_novelty(articles)

            out = {
                "pair": pair,
                "ticker": ticker,
                "date_window": date_window,
                "items": len(articles),
                "bias": round(bias, 2),       # [-1..+1]
                "novelty": round(novelty, 2), # [0..0.5]
                "articles": [_trim_article(a) for a in articles[:100]],  # cap
            }

            out_path = Path(f"data/news/{pair}.json")
            out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
            print(
                f"[NEWS-REFRESH] {pair} bias={out['bias']:+.2f} "
                f"novelty={out['novelty']:.2f} -> {out_path}"
            )

        except Exception as e:
            print(f"[NEWS-REFRESH][ERROR] {pair}: {e!r}")


def parse_args():
    p = argparse.ArgumentParser(description="Refresh CryptoNews articles per pair.")
    p.add_argument(
        "--pairs",
        nargs="*",
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"],
        help="Trading pairs (default: common top6).",
    )
    p.add_argument("--items", type=int, default=50, help="Items per ticker page.")
    p.add_argument(
        "--date",
        dest="date_window",
        default="last60min",
        help="Provider date window (e.g., last60min, last24hours).",
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
    run(args.pairs, args.items, args.date_window, args.page, args.cache)
