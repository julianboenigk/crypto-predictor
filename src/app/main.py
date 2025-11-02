# src/app/main.py
from __future__ import annotations

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timezone

# --- .env auto-load ---
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"

# --------- Defaults ----------
DEFAULT_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
DEFAULT_INTERVAL = "15m"
DEFAULT_THRESHOLDS = {"long": 0.40, "short": -0.40}
DEFAULT_WEIGHTS = {"technical": 0.55, "news": 0.45}
DEFAULT_MAX_AGE_SEC = 180  # will be expanded by interval

# --------- YAML --------------
def _read_yaml(path: Path) -> Optional[dict]:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
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
        return DEFAULT_WEIGHTS.copy()
    return {str(k).lower(): float(v) for k, v in data.items() if isinstance(v, (int, float))}


def load_thresholds() -> Dict[str, float]:
    data = _read_yaml(CONFIG_DIR / "thresholds.yaml")
    if not data:
        return DEFAULT_THRESHOLDS.copy()
    c = data.get("consensus") or {}
    return {"long": float(c.get("long", 0.40)), "short": float(c.get("short", -0.40))}


# --------- Pretty Notifier (STRICT import) ----------
from src.core.notify import send_telegram, format_signal_message

# --------- Agents -----------
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

# --------- Data fetch -------
_get_ohlcv = None
try:
    from src.data.binance_client import get_ohlcv as _get_ohlcv  # type: ignore
except Exception as e:
    print(f"[WARN] get_ohlcv unavailable: {e}", file=sys.stderr)


def _fetch_rows(pair: str, interval: str, limit: int = 300) -> Any:
    if callable(_get_ohlcv):
        try:
            return _get_ohlcv(pair, interval, limit=limit)
        except Exception as e:
            print(f"[WARN] get_ohlcv({pair},{interval}) failed: {e}", file=sys.stderr)
    return None


def _rows_to_tech_candles(rows: Any) -> Optional[List[dict]]:
    """Convert Binance kline rows into the structure TechnicalAgent expects."""
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], (list, tuple)):
        return None
    out: List[dict] = []
    for r in rows:
        if len(r) < 7:
            continue
        try:
            out.append({"c": float(r[4]), "h": float(r[2]), "low": float(r[3])})
        except Exception:
            return None
    return out or None


def _latest_ts_from_rows(rows: Any) -> Optional[float]:
    try:
        if isinstance(rows, list) and rows and isinstance(rows[0], (list, tuple)):
            v = rows[-1][6] if len(rows[-1]) >= 7 else rows[-1][0]
            v = float(v)
            return v / (1000.0 if v > 10_000_000_000 else 1.0)
    except Exception:
        pass
    return None


def _is_fresh(ts_sec: Optional[float], max_age_sec: int) -> bool:
    if ts_sec is None:
        return False
    now = datetime.now(timezone.utc).timestamp()
    return (now - ts_sec) <= max_age_sec


def _interval_to_seconds(interval: str) -> int:
    m = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "3d": 259200,
        "1w": 604800,
        "1M": 2592000,
    }
    return m.get(interval, 900)


def _effective_freshness_sec(user_max_age_sec: int, interval: str) -> int:
    interval_sec = _interval_to_seconds(interval)
    return max(user_max_age_sec, interval_sec + 60)


# --------- Consensus --------
def _normalize_weights(w: Dict[str, float]) -> Dict[str, float]:
    total = sum(max(0.0, float(v)) for v in w.values())
    return {k: (max(0.0, float(v)) / total if total > 0 else 0.0) for k, v in w.items()}


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
    breakdown = []
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
    if S >= thresholds["long"]:
        return S, "LONG", "consensus ≥ long", breakdown
    if S <= thresholds["short"]:
        return S, "SHORT", "consensus ≤ short", breakdown
    return S, "HOLD", "within band", breakdown


# --------- Collect votes ----
def collect_votes(universe: List[str], interval: str, asof: datetime, max_age_sec: int) -> List[Dict[str, Any]]:
    votes: List[Dict[str, Any]] = []
    eff_max_age_sec = _effective_freshness_sec(max_age_sec, interval)

    # technical per pair
    if TechnicalAgent is not None and callable(_get_ohlcv):
        ta = TechnicalAgent()
        for pair in universe:
            rows = _fetch_rows(pair, interval, 300)
            latest = _latest_ts_from_rows(rows)
            fresh = _is_fresh(latest, eff_max_age_sec)
            candles = _rows_to_tech_candles(rows)
            if not candles:
                print(f"[WARN] {pair}: no candles after transform", file=sys.stderr)
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
    elif TechnicalAgent is not None:
        print("[WARN] TechnicalAgent present but no OHLCV fetcher found", file=sys.stderr)

    # news batch (optional)
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

    return votes


# --------- Run once ----------
def run_once() -> None:
    asof = datetime.now(timezone.utc)
    pairs, interval, max_age_sec = load_universe()
    weights = load_weights()
    thresholds = load_thresholds()

    t0 = time.time()
    votes = collect_votes(pairs, interval, asof, max_age_sec)

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
                "latency_ms": int((time.time() - t0) * 1000),
            }
        )

        # --- new feature: only send non-HOLD if SEND_HOLD=false ---
        if os.getenv("SEND_HOLD", "true").lower() != "true" and decision.upper() == "HOLD":
            continue

        msg = format_signal_message(pair, decision, S, breakdown, reason)
        send_telegram(msg, parse_mode="Markdown")

    # persist + print summary
    try:
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        with (ROOT / "data" / "runs.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run_at": asof.isoformat(), "results": results}) + "\n")
    except Exception:
        pass

    print(json.dumps({"run_at": asof.isoformat(), "n_pairs": len(pairs), "latency_ms": int((time.time() - t0) * 1000)}))


# --------- CLI ---------------
def _usage() -> None:
    print("Usage:\n  python -m src.app.main run\n  python -m src.app.main pair BTCUSDT")


def _debug_pair(pair: str) -> None:
    asof = datetime.now(timezone.utc)
    pairs, interval, max_age_sec = load_universe()
    weights = load_weights()
    thresholds = load_thresholds()
    votes = collect_votes([pair], interval, asof, max_age_sec)
    S, decision, reason, breakdown = decide_pair(pair, votes, weights, thresholds)
    print(
        json.dumps(
            {"pair": pair, "score": round(S, 6), "decision": decision, "reason": reason, "breakdown": breakdown, "weights": weights},
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
