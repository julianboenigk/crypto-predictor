# src/app/main.py
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"

DEFAULT_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"]
DEFAULT_INTERVAL = "15m"
DEFAULT_MAX_AGE_SEC = 900

# Defaults nur als Fallback; eigentliche Werte kommen aus configs/weights.yaml & thresholds.yaml
DEFAULT_WEIGHTS = {
    "technical": 0.60,
    "sentiment": 0.15,
    "news": 0.15,
    "research": 0.10,
}

DEFAULT_THRESHOLDS = {
    "long": 0.85,
    "short": -0.85,
}

# Trendfilter: wie stark muss Technical sein, um LONG/SHORT zu erlauben?
MIN_TREND_SCORE = float(os.getenv("MIN_TREND_SCORE", "0.2"))

# Agents
try:
    from src.agents.technical import TechnicalAgent  # type: ignore
except Exception as e:
    print(f"[WARN] import TechnicalAgent failed: {e}", file=sys.stderr)
    TechnicalAgent = None  # type: ignore

try:
    from src.agents.news import NewsAgent  # type: ignore
except Exception as e:
    print(f"[WARN] import NewsAgent failed: {e}", file=sys.stderr)
    NewsAgent = None  # type: ignore

try:
    from src.agents.sentiment import SentimentAgent  # type: ignore
except Exception as e:
    print(f"[WARN] import SentimentAgent failed: {e}", file=sys.stderr)
    SentimentAgent = None  # type: ignore

try:
    from src.agents.research import ResearchAgent  # type: ignore
except Exception as e:
    print(f"[WARN] import ResearchAgent failed: {e}", file=sys.stderr)
    ResearchAgent = None  # type: ignore

# data
_get_ohlcv = None
try:
    from src.data.binance_client import get_ohlcv as _get_ohlcv  # type: ignore
except Exception as e:
    print(f"[WARN] get_ohlcv unavailable: {e}", file=sys.stderr)

# notify
try:
    from src.core.notify import format_signal_message, send_telegram  # type: ignore
except Exception as e:
    print(f"[WARN] notify import failed: {e}", file=sys.stderr)
    format_signal_message = None  # type: ignore
    send_telegram = None  # type: ignore

# paper trading
try:
    from src.trade.risk import compute_order_levels  # type: ignore
    from src.trade.paper import open_paper_trade  # type: ignore
    PAPER_ENABLED = True
except Exception:
    PAPER_ENABLED = False

# dynamic weights
try:
    from src.core.weights import compute_dynamic_weights  # type: ignore
    DYN_WEIGHTS_AVAILABLE = True
except Exception:
    DYN_WEIGHTS_AVAILABLE = False


def _read_yaml(path: Path) -> Optional[dict]:
    import yaml
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def load_universe() -> Tuple[List[str], str, int]:
    cfg = _read_yaml(CONFIG_DIR / "universe.yaml") or {}
    pairs = cfg.get("pairs") or DEFAULT_UNIVERSE
    interval = cfg.get("interval") or DEFAULT_INTERVAL
    max_age = int(cfg.get("max_input_age_sec", DEFAULT_MAX_AGE_SEC))
    env_uni = os.getenv("UNIVERSE")
    if env_uni:
        pairs = [p.strip().upper() for p in env_uni.split(",") if p.strip()]
    return pairs, interval, max_age


def load_weights() -> Dict[str, float]:
    data = _read_yaml(CONFIG_DIR / "weights.yaml")
    if not data:
        return {k: float(v) for k, v in DEFAULT_WEIGHTS.items()}
    return {str(k).lower(): float(v) for k, v in data.items() if isinstance(v, (int, float))}


def load_thresholds() -> Dict[str, float]:
    data = _read_yaml(CONFIG_DIR / "thresholds.yaml")
    if not data:
        return DEFAULT_THRESHOLDS.copy()
    cons = data.get("consensus") or data
    return {
        "long": float(cons.get("long", DEFAULT_THRESHOLDS["long"])),
        "short": float(cons.get("short", DEFAULT_THRESHOLDS["short"])),
    }


def load_telegram_score_min() -> float:
    env_val = os.getenv("TELEGRAM_SCORE_MIN")
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    notif_cfg = _read_yaml(CONFIG_DIR / "notifications.yaml") or {}
    if "score_min" in notif_cfg:
        try:
            return float(notif_cfg["score_min"])
        except ValueError:
            pass
    # Default eher konservativ
    return 0.85


def _fetch_rows(pair: str, interval: str, limit: int = 300) -> Any:
    if callable(_get_ohlcv):
        try:
            return _get_ohlcv(pair, interval, limit=limit)
        except Exception as e:
            print(f"[WARN] get_ohlcv({pair},{interval}) failed: {e}", file=sys.stderr)
    return None


def _rows_to_tech_candles(rows: Any) -> Optional[List[dict]]:
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], (list, tuple)):
        return None
    out: List[dict] = []
    for r in rows:
        if len(r) < 7:
            continue
        out.append(
            {
                "t": int(r[0]) // 1000,
                "o": float(r[1]),
                "h": float(r[2]),
                "low": float(r[3]),
                "c": float(r[4]),
                "v": float(r[5]),
            }
        )
    return out


def _latest_ts_from_rows(rows: Any) -> Optional[float]:
    if not rows:
        return None
    try:
        return rows[-1][0] / 1000.0
    except Exception:
        return None


def _latest_close_from_rows(rows: Any) -> Optional[float]:
    if not rows:
        return None
    try:
        return float(rows[-1][4])
    except Exception:
        return None


def _interval_to_seconds(interval: str) -> int:
    m = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
    }
    return m.get(interval, 900)


def _effective_freshness_sec(max_age_sec: int, interval: str) -> int:
    return max(max_age_sec, 2 * _interval_to_seconds(interval))


def _is_fresh(ts_sec: Optional[float], max_age_sec: int) -> bool:
    if ts_sec is None:
        return False
    now = datetime.now(timezone.utc).timestamp()
    return (now - ts_sec) <= max_age_sec


def _normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    total = sum(w.values())
    if total <= 0:
        return w
    return {k: v / total for k, v in w.items()}


def decide_pair(
    pair: str,
    votes: List[Dict[str, Any]],
    weights: Dict[str, float],
    thresholds: Dict[str, float],
) -> Tuple[float, str, str, List[Tuple[str, float, float]]]:
    by_agent: Dict[str, Dict[str, Any]] = {}
    for v in votes:
        if v.get("pair") == pair:
            by_agent[str(v.get("agent", "unknown")).lower()] = v

    norm_w = _normalize_weights(weights)
    participating = {a: w for a, w in norm_w.items() if a in by_agent and w > 0}
    if not participating:
        return 0.0, "HOLD", "no agent outputs", [("none", 0.0, 0.0)]

    num = 0.0
    den = 0.0
    fresh_all = True
    breakdown: List[Tuple[str, float, float]] = []
    for agent, w in participating.items():
        r = by_agent[agent]
        s = float(r.get("score", 0.0))
        c = float(r.get("confidence", 0.0))
        fr = bool(r.get("inputs_fresh", False))
        if not fr:
            fresh_all = False
        num += w * s * c
        den += w * c
        breakdown.append((agent, s, c))

    S = num / den if den > 0 else 0.0

    if not fresh_all:
        return S, "HOLD", "stale inputs", breakdown

    long_thr = float(thresholds.get("long", DEFAULT_THRESHOLDS["long"]))
    short_thr = float(thresholds.get("short", DEFAULT_THRESHOLDS["short"]))

    # Trendfilter: Technical muss LONG/SHORT klar unterstützen
    tech_vote = by_agent.get("technical")
    if tech_vote is not None:
        tech_s = float(tech_vote.get("score", 0.0))
        # LONG nur, wenn Technical klar positiv ist
        if S >= long_thr and tech_s < MIN_TREND_SCORE:
            return S, "HOLD", "trend_filter_long", breakdown
        # SHORT nur, wenn Technical klar negativ ist
        if S <= short_thr and tech_s > -MIN_TREND_SCORE:
            return S, "HOLD", "trend_filter_short", breakdown

    if S >= long_thr:
        return S, "LONG", "ok", breakdown
    if S <= short_thr:
        return S, "SHORT", "ok", breakdown
    return S, "HOLD", "ok", breakdown


def collect_votes(
    universe: List[str],
    interval: str,
    asof: datetime,
    max_age_sec: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    votes: List[Dict[str, Any]] = []
    eff_max_age_sec = _effective_freshness_sec(max_age_sec, interval)
    last_prices: Dict[str, float] = {}

    if TechnicalAgent is not None and callable(_get_ohlcv):
        ta = TechnicalAgent()
        for pair in universe:
            rows = _fetch_rows(pair, interval, 300)
            latest_ts = _latest_ts_from_rows(rows)
            latest_close = _latest_close_from_rows(rows)
            if latest_close is not None:
                last_prices[pair] = latest_close
            fresh = _is_fresh(latest_ts, eff_max_age_sec)
            candles = _rows_to_tech_candles(rows)
            if not candles:
                continue
            try:
                res = ta.run(pair, candles, fresh)
                if isinstance(res, dict):
                    res.setdefault("agent", "technical")
                    res.setdefault("inputs_fresh", fresh)
                    res.setdefault("pair", pair)
                    votes.append(res)
            except Exception as e:
                print(f"[WARN] TechnicalAgent.run failed for {pair}: {e}", file=sys.stderr)

    if NewsAgent is not None:
        try:
            na = NewsAgent()
            out = na.run(universe, asof)
            for r in out:
                r.setdefault("agent", "news")
                r.setdefault("inputs_fresh", True)
                votes.append(r)
        except Exception as e:
            print(f"[WARN] NewsAgent.run failed: {e}", file=sys.stderr)

    if SentimentAgent is not None:
        try:
            sa = SentimentAgent()
            out = sa.run(universe, asof)
            for r in out:
                r.setdefault("agent", "sentiment")
                votes.append(r)
        except Exception as e:
            print(f"[WARN] SentimentAgent.run failed: {e}", file=sys.stderr)

    if ResearchAgent is not None:
        try:
            ra = ResearchAgent()
            out = ra.run(universe, asof)
            for r in out:
                r.setdefault("agent", "research")
                votes.append(r)
        except Exception as e:
            print(f"[WARN] ResearchAgent.run failed: {e}", file=sys.stderr)

    return votes, last_prices


def run_once() -> None:
    asof = datetime.now(timezone.utc)
    pairs, interval, max_age_sec = load_universe()
    base_weights = load_weights()
    thresholds = load_thresholds()
    telegram_score_min = load_telegram_score_min()

    if DYN_WEIGHTS_AVAILABLE and os.getenv("DYNAMIC_WEIGHTS", "true").lower() == "true":
        weights = compute_dynamic_weights(base=base_weights)
    else:
        weights = base_weights

    t0 = time.time()
    votes, last_prices = collect_votes(pairs, interval, asof, max_age_sec)

    results: List[Dict[str, Any]] = []
    for pair in pairs:
        S, decision, reason, breakdown = decide_pair(pair, votes, weights, thresholds)
        results.append(
            {
                "t": asof.isoformat(),
                "pair": pair,
                "score": round(S, 6),
                "decision": decision,
                "reason": reason,
                "breakdown": breakdown,
                "weights": weights,
                "interval": interval,
                "last_price": last_prices.get(pair),
                "latency_ms": int((time.time() - t0) * 1000),
            }
        )

    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (DATA_DIR / "runs.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run_at": asof.isoformat(), "results": results}) + "\n")
    except Exception:
        pass

    if format_signal_message and send_telegram:
        for res in results:
            if res["decision"] in ("LONG", "SHORT") and abs(res["score"]) >= telegram_score_min:
                order_levels = None
                if PAPER_ENABLED:
                    price = res.get("last_price")
                    if price is not None:
                        order_levels = compute_order_levels(
                            side=res["decision"],
                            price=price,
                            risk_pct=0.01,
                            rr=1.5,
                            sl_distance_pct=0.004,
                        )
                        open_paper_trade(
                            pair=res["pair"],
                            side=order_levels["side"],
                            entry=order_levels["entry"],
                            stop_loss=order_levels["stop_loss"],
                            take_profit=order_levels["take_profit"],
                            size=1.0,
                            meta={
                                "score": res["score"],
                                "reason": res["reason"],
                                "breakdown": res["breakdown"],
                            },
                        )

                msg = format_signal_message(
                    res["pair"],
                    res["decision"],
                    res["score"],
                    res["breakdown"],
                    res["reason"],
                    order_levels=order_levels,
                )
                send_telegram(msg)

    print(
        json.dumps(
            {
                "run_at": asof.isoformat(),
                "n_pairs": len(pairs),
                "latency_ms": int((time.time() - t0) * 1000),
            }
        )
    )


def _usage() -> None:
    print("Usage: python -m src.app.main run | pair BTCUSDT")


def _debug_pair(pair: str) -> None:
    asof = datetime.now(timezone.utc)
    pairs, interval, max_age_sec = load_universe()
    base_weights = load_weights()
    if DYN_WEIGHTS_AVAILABLE and os.getenv("DYNAMIC_WEIGHTS", "true").lower() == "true":
        weights = compute_dynamic_weights(base=base_weights)
    else:
        weights = base_weights
    thresholds = load_thresholds()
    votes, _ = collect_votes([pair], interval, asof, max_age_sec)
    S, decision, reason, breakdown = decide_pair(pair, votes, weights, thresholds)
    print(
        json.dumps(
            {
                "pair": pair,
                "score": round(S, 6),
                "decision": decision,
                "reason": reason,
                "breakdown": breakdown,
                "weights": weights,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)
    cmd = sys.argv[1].lower()
    if cmd == "run":
        run_once()
    elif cmd == "pair" and len(sys.argv) >= 3:
        _debug_pair(sys.argv[2].upper())
    else:
        _usage()
        sys.exit(1)
