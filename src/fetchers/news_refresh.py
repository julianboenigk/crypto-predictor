# src/fetchers/news_refresh.py
# Pulls CryptoNews article lists per symbol and writes normalized JSON.
# Computes a lightweight bias/novelty heuristic for quick scoring.

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from typing import List, Dict, Any

# Best-effort .env loading (won’t crash if not present)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from src.providers.cryptonews import (
    fetch_news_list,
)

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


def _safe_title(item: Dict[str, Any]) -> str:
    return str(
        item.get("title")
        or item.get("news_title")
        or item.get("headline")
        or ""
    ).strip()


def _get_source(item: Dict[str, Any]) -> str:
    return str(
        item.get("source")
        or item.get("source_name")
        or item.get("publisher")
        or ""
    ).strip().lower()


def _compute_bias_and_novelty(articles: List[Dict[str, Any]]) -> (float, float):
    """
    Heuristic:
      - bias: simple keyword sentiment over titles only (very lightweight, deterministic).
      - novelty: unique sources / total, clamped to [0, 0.50] to match earlier log style.

    This is intentionally simple to avoid external NLP deps.
    """
    if not articles:
        return 0.0, 0.0

    pos_kw = ("surge", "record", "bull", "rally", "soar", "approve", "growth", "rise", "win", "support", "breakout")
    neg_kw = ("drop", "falls", "bear", "lawsuit", "ban", "hack", "decline", "risk", "loss", "bearish", "downturn")

    score = 0
    for a in articles:
        title = _safe_title(a).lower()
        if not title:
            continue
        if any(k in title for k in pos_kw):
            score += 1
        if any(k in title for k in neg_kw):
            score -= 1

    n = len(articles)
    bias = 0.0 if n == 0 else max(-1.0, min(1.0, score / max(3.0, n / 3.0)))  # soften extremes

    sources = [_get_source(a) for a in articles if _get_source(a)]
    uniq = len(set(sources))
    novelty = min(0.50, (uniq / max(1, n)))  # keep 0..0.5 range to mirror your prior logs

    # round for stable logging
    return round(bias, 2), round(novelty, 2)


def refresh_news(
    symbols: List[str],
    date_window: str,
    out_dir: str,
    items: int = 50,
    page: int = 1,
    cache: bool = False,
) -> None:
    _ensure_dir(out_dir)

    for sym in symbols:
        try:
            articles = fetch_news_list(
                sym,
                date_window=date_window,
                items=items,
                page=page,
                cache=cache,
            )
            bias, novelty = _compute_bias_and_novelty(articles)

            payload = {
                "symbol": sym,
                "provider": "cryptonews/news",
                "date_window": date_window,
                "count": len(articles),
                "bias": bias,        # lightweight heuristic
                "novelty": novelty,  # 0..0.5
                "articles": articles,  # keep raw list for transparency
                "ts": _now_iso(),
            }

            out_path = os.path.join(out_dir, f"{sym}.json")
            _write_json(out_path, payload)
            print(f"[NEWS-REFRESH] {sym} bias={bias:+.2f} novelty={novelty:.2f} -> {out_path}")
        except Exception as e:
            print(f"[NEWS-REFRESH][ERROR] {sym}: {repr(e)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Refresh CryptoNews articles and write normalized JSON with bias/novelty heuristics."
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
        default="last60min",
        choices=sorted(ALLOWED_WINDOWS),
        help="Date window per provider docs (default: last60min).",
    )
    p.add_argument(
        "--items",
        type=int,
        default=50,
        help="Number of items per call (default: 50).",
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
        default="data/news",
        help="Output directory (default: data/news).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    refresh_news(
        symbols=symbols,
        date_window=args.date_window,
        out_dir=args.outdir,
        items=args.items,
        page=args.page,
        cache=args.cache,
    )


if __name__ == "__main__":
    main()
