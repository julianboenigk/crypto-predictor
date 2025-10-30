from __future__ import annotations

import json, math, time
from pathlib import Path
from typing import Any, Dict, List, Optional

USE_NEWS_CACHE = True  # reuse articles saved by news_refresh (no extra API calls)
DATA_DIR = Path("data")
NEWS_DIR = DATA_DIR / "news"
SENT_DIR = DATA_DIR / "sentiment"
SENT_DIR.mkdir(parents=True, exist_ok=True)

PAIRS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT"]

def _now_ms() -> int: return int(time.time() * 1000)

def _load_articles_from_cache(pair: str) -> List[Dict[str, Any]]:
    f = NEWS_DIR / f"{pair}.json"
    if not f.exists(): return []
    try:
        payload = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = payload.get("items", [])
    return items if isinstance(items, list) else []

def _extract_article_sentiment(a: Dict[str, Any]) -> Optional[float]:
    for key in ("overall_sentiment_score","sentiment_score","sentiment","score"):
        if key in a:
            try:
                val = float(a[key])
                if -1.0 <= val <= 1.0: return val
                if 0.0 <= val <= 1.0: return val * 2.0 - 1.0
                if -100.0 <= val <= 100.0: return val / 100.0
                return math.tanh(val)
            except Exception:
                pass
    return None

_POS = {"surge","rally","bull","bullish","breakout","partnership","upgrade","adoption","record","all-time","ath","win","approve"}
_NEG = {"plunge","crash","bear","bearish","hack","exploit","ban","lawsuit","fraud","delay","reject","downgrade"}

def _fallback_keyword_sentiment(a: Dict[str, Any]) -> Optional[float]:
    text = " ".join(str(a.get(k, "")) for k in ("title","text","description","summary")).lower()
    if not text.strip(): return None
    pos_hits = sum(1 for w in _POS if w in text)
    neg_hits = sum(1 for w in _NEG if w in text)
    if pos_hits == 0 and neg_hits == 0: return 0.0
    score = (pos_hits - neg_hits) / max(1.0, pos_hits + neg_hits)
    return max(-1.0, min(1.0, score))

def _aggregate_sentiment(arts: List[Dict[str, Any]]) -> Dict[str, float]:
    scores: List[float] = []
    for a in arts:
        s = _extract_article_sentiment(a)
        if s is None: s = _fallback_keyword_sentiment(a)
        if s is not None: scores.append(max(-1.0, min(1.0, float(s))))
    n, n_scored = len(arts), len(scores)
    if n_scored == 0:
        return {"polarity": 0.0, "volume_z": 0.0, "signal": 0.5}
    polarity = sum(scores) / n_scored
    baseline, stdev = 12.0, 5.0
    volume_z = max(-3.0, min(3.0, (n - baseline) / stdev))
    strong = sum(1 for s in scores if abs(s) >= 0.3)
    consistency = strong / n_scored
    signal = 0.4 + 0.5 * consistency + 0.1 * min(1.0, n / 20.0)
    signal = max(0.0, min(1.0, signal))
    return {"polarity": polarity, "volume_z": volume_z, "signal": signal}

def refresh_one(pair: str) -> None:
    arts = _load_articles_from_cache(pair) if USE_NEWS_CACHE else _load_articles_from_cache(pair)
    agg = _aggregate_sentiment(arts)
    out = {"ts": _now_ms(), "polarity": round(agg["polarity"], 4), "volume_z": round(agg["volume_z"], 2), "signal": round(agg["signal"], 2)}
    out_path = SENT_DIR / f"{pair}.json"
    out_path.write_text(json.dumps(out), encoding="utf-8")
    print(f"[SENT-REFRESH] {pair} pol={out['polarity']:+.2f} vz={out['volume_z']:+.2f} sig={out['signal']:.2f} -> {out_path}")

def main() -> int:
    for pair in PAIRS:
        try: refresh_one(pair)
        except Exception as e: print(f"[SENT-REFRESH][ERROR] {pair}: {e}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
