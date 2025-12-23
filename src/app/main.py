# src/app/main.py
from __future__ import annotations

# ============================================================
# BOOTSTRAP ENV (einmal, zentral)
# ============================================================
from src.bootstrap.env import PROJECT_ROOT  # noqa: F401  (loads .env via side-effect)

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.consensus import decide_pair
from src.tools.log_rotation import maybe_rotate_all_logs

# ============================================================
# Environment / Runtime
# ============================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "paper").lower()
if ENVIRONMENT not in ("paper", "testnet", "live"):
    ENVIRONMENT = "paper"

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
TRADING_HARD_STOP = os.getenv("TRADING_HARD_STOP", "false").lower() == "true"

FINAL_SCORE_MIN = float(os.getenv("FINAL_SCORE_MIN", "0.6"))

# ============================================================
# Paths
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "configs"

# ============================================================
# External integrations (optional)
# ============================================================

# Market data
try:
    from src.data.binance_client import get_ohlcv  # type: ignore
except Exception as e:
    print(f"[WARN] get_ohlcv import failed: {e}", file=sys.stderr)
    get_ohlcv = None  # type: ignore

# Telegram
try:
    from src.core.notify import format_signal_message, send_telegram  # type: ignore
except Exception as e:
    print(f"[WARN] notify import failed: {e}", file=sys.stderr)
    format_signal_message = None  # type: ignore
    send_telegram = None  # type: ignore

# Paper trading
try:
    from src.trade.paper import open_paper_trade  # type: ignore
    from src.trade.risk import compute_order_levels  # type: ignore

    PAPER_ENABLED = True
except Exception as e:
    print(f"[WARN] paper trading imports failed: {e}", file=sys.stderr)
    PAPER_ENABLED = False

# ============================================================
# Config loaders
# ============================================================


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml

        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_universe() -> Tuple[List[str], str, int]:
    cfg = _read_yaml(CONFIG_DIR / "universe.yaml")
    pairs = cfg.get("pairs", ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT"])
    interval = cfg.get("interval", "15m")
    max_age = int(cfg.get("max_input_age_sec", 900))

    env_pairs = os.getenv("UNIVERSE")
    if env_pairs:
        pairs = [p.strip().upper() for p in env_pairs.split(",") if p.strip()]

    return pairs, interval, max_age


def load_thresholds() -> Dict[str, float]:
    env_long = os.getenv("CONSENSUS_LONG")
    env_short = os.getenv("CONSENSUS_SHORT")

    if env_long is not None and env_short is not None:
        try:
            return {"long": float(env_long), "short": float(env_short)}
        except ValueError:
            pass

    cfg = _read_yaml(CONFIG_DIR / "thresholds.yaml")
    c = cfg.get("consensus", cfg)

    long_v = c.get("long", 0.6)
    short_v = c.get("short", -0.6)

    try:
        long_thr = float(long_v)
    except Exception:
        long_thr = 0.6

    try:
        short_thr = float(short_v)
    except Exception:
        short_thr = -0.6

    return {"long": long_thr, "short": short_thr}


# ============================================================
# Agents
# ============================================================


def load_agents():
    from src.agents.technical import TechnicalAgent
    from src.agents.ai_news_sentiment import AINewsSentimentAgent

    return [
        TechnicalAgent(),
        AINewsSentimentAgent(),
    ]


# ============================================================
# Market data helpers
# ============================================================


def _rows_to_candles(rows: Any) -> Optional[List[dict]]:
    """
    Binance klines: [open_time, open, high, low, close, volume, ...]
    Liefert ein Candle-Dict, das sowohl "verbose" als auch "short" Keys enthält,
    damit TechnicalAgent (egal ob er close/low oder c/l erwartet) stabil läuft.
    """
    if not isinstance(rows, list) or not rows:
        return None

    out: List[dict] = []
    for r in rows:
        if not isinstance(r, (list, tuple)) or len(r) < 6:
            continue
        try:
            t = int(r[0]) // 1000
            o = float(r[1])
            h = float(r[2])
            lo = float(r[3])
            cl = float(r[4])
            v = float(r[5])
        except Exception:
            continue

        out.append(
            {
                "t": t,
                # verbose keys
                "open": o,
                "high": h,
                "low": lo,
                "close": cl,
                "volume": v,
                # short keys
                "o": o,
                "h": h,
                "l": lo,
                "c": cl,
                "v": v,
            }
        )

    return out or None


# ============================================================
# Vote collection
# ============================================================

def collect_votes(
    pairs: List[str],
    interval: str,
    asof: datetime,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    votes: List[Dict[str, Any]] = []
    last_prices: Dict[str, float] = {}
    candles_map: Dict[str, List[dict]] = {}

    if not callable(get_ohlcv):
        print("[WARN] get_ohlcv not available", file=sys.stderr)
        return votes, last_prices

    # --- load market data
    for pair in pairs:
        try:
            rows = get_ohlcv(pair, interval, limit=300)
        except Exception as e:
            print(f"[WARN] get_ohlcv failed for {pair}: {e}", file=sys.stderr)
            continue

        candles = _rows_to_candles(rows)
        if not candles:
            print(f"[WARN] No candles for {pair}", file=sys.stderr)
            continue

        candles_map[pair] = candles

        try:
            last_prices[pair] = float(candles[-1]["c"])
        except Exception:
            print(f"[WARN] Missing last close for {pair}", file=sys.stderr)
            continue

    # --- agents
    agents = load_agents()

    for agent in agents:
        agent_name = getattr(agent, "agent_name", agent.__class__.__name__).lower().strip()

        # TechnicalAgent → per pair
        if agent_name.startswith("technical"):
            for pair, candles in candles_map.items():
                try:
                    out = agent.run(pair, candles, True)
                except Exception as e:
                    print(f"[WARN] TechnicalAgent.run failed for {pair}: {e}", file=sys.stderr)
                    continue

                if not isinstance(out, dict):
                    print(f"[WARN] TechnicalAgent.run returned non-dict for {pair}: {type(out)}", file=sys.stderr)
                    continue

                # DEFENSIV: copy to avoid shared dict references
                v = dict(out)

                # HARD SET (kein setdefault)
                v["agent"] = "technical"
                v["pair"] = pair
                v["inputs_fresh"] = bool(v.get("inputs_fresh", True))

                votes.append(v)

        # AI agents → universe wide
        else:
            try:
                outputs = agent.run(pairs, asof)
            except Exception as e:
                print(f"[WARN] {agent_name}.run failed: {e}", file=sys.stderr)
                continue

            if not outputs:
                continue

            for out in outputs:
                if not isinstance(out, dict):
                    continue

                v = dict(out)  # copy

                # MUSS pair haben, sonst wird decide_pair zwangsläufig Mist bauen
                pair = v.get("pair")
                if not isinstance(pair, str) or not pair.strip():
                    print(f"[WARN] {agent_name} output missing 'pair': {v}", file=sys.stderr)
                    continue

                v["pair"] = pair.strip().upper()
                v["agent"] = v.get("agent", agent_name) or agent_name
                v["inputs_fresh"] = bool(v.get("inputs_fresh", True))

                votes.append(v)

    return votes, last_prices


def _agent_outputs_for_pair(pair: str, votes: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    agent_outputs Format:
      { "technical": {"score": x, "confidence": y}, "news_sentiment": {...} }
    Nimmt den letzten Vote pro Agent für dieses Pair.
    """
    out: Dict[str, Dict[str, float]] = {}
    for v in votes:
        if v.get("pair") != pair:
            continue
        agent = str(v.get("agent", "")).strip()
        if not agent:
            continue
        try:
            score = float(v.get("score", 0.0))
        except Exception:
            score = 0.0
        try:
            conf = float(v.get("confidence", 0.0))
        except Exception:
            conf = 0.0
        out[agent] = {"score": score, "confidence": conf}
    return out


# ============================================================
# Main execution
# ============================================================


def run_once(single_pair: Optional[str] = None, backtest_mode: bool = False) -> List[Dict[str, Any]]:
    asof = datetime.now(timezone.utc)
    t0 = time.time()

    maybe_rotate_all_logs()

    pairs, interval, _ = load_universe()
    if single_pair:
        pairs = [single_pair]

    thresholds = load_thresholds()

    votes, last_prices = collect_votes(pairs, interval, asof)

    #debut script

    # DEBUG: Stimmen die Votes pro Pair überhaupt?
    from collections import defaultdict

    by_pair = defaultdict(list)
    for v in votes:
        by_pair[str(v.get("pair"))].append(v)

    print("[DEBUG] votes total:", len(votes), file=sys.stderr)
    for p in pairs:
        vs = by_pair.get(p, [])
        tech = [x for x in vs if x.get("agent") == "technical"]
        ns   = [x for x in vs if x.get("agent") == "news_sentiment"]
        tech_last = tech[-1] if tech else {}
        print(
            f"[DEBUG] {p}: votes={len(vs)} tech_score={tech_last.get('score')} tech_conf={tech_last.get('confidence')} news_votes={len(ns)}",
            file=sys.stderr,
        )

    results: List[Dict[str, Any]] = []

    for pair in pairs:
        # src.core.consensus.decide_pair signature: (pair, votes, thresholds)
        score, decision, reason, contributions = decide_pair(pair, votes, thresholds)

        results.append(
            {
                "t": asof.isoformat(),
                "pair": pair,
                "score": float(round(score, 6)),
                "decision": decision,
                "reason": reason,
                "breakdown": contributions,  # dict {agent: contribution}
                "last_price": last_prices.get(pair),
                "interval": interval,
                "latency_ms": int((time.time() - t0) * 1000),
            }
        )

    # --- log run
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (DATA_DIR / "runs.log").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"run_at": asof.isoformat(), "results": results}) + "\n")
    except Exception as e:
        print(f"[WARN] writing runs.log failed: {e}", file=sys.stderr)

    # --- act on decisions (skip in backtest mode)
    if not backtest_mode and PAPER_ENABLED and not TRADING_HARD_STOP:
        for r in results:
            if r["decision"] not in ("LONG", "SHORT"):
                continue

            score_abs = abs(float(r["score"]))
            if score_abs < FINAL_SCORE_MIN:
                continue

            price = r.get("last_price")
            if price is None:
                continue

            levels = compute_order_levels(
                side=r["decision"],
                price=float(price),
                risk_pct=0.01,
                rr=1.5,
                sl_distance_pct=0.004,
            )

            open_paper_trade(
                pair=r["pair"],
                side=levels["side"],
                entry=levels["entry"],
                stop_loss=levels["stop_loss"],
                take_profit=levels["take_profit"],
                size=1.0,
                meta={
                    "entry_ts": asof.isoformat(),
                    "entry_score": r["score"],
                    "agent_outputs": _agent_outputs_for_pair(r["pair"], votes),
                    "decision": r["decision"],
                    "reason": r["reason"],
                },
            )

            if send_telegram and format_signal_message:
                msg = format_signal_message(
                    r["pair"],
                    r["decision"],
                    r["score"],
                    r["breakdown"],
                    r["reason"],
                    order_levels=levels,
                )
                send_telegram(msg)

    # Always print for CLI usage
    print(json.dumps({"run_at": asof.isoformat(), "results": results}, indent=2))

    return results


# ============================================================
# CLI
# ============================================================


def _usage() -> None:
    print("Usage: python -m src.app.main run | pair BTCUSDT | backtest")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "run":
        run_once()

    elif cmd == "pair" and len(sys.argv) >= 3:
        run_once(single_pair=sys.argv[2].upper())

    elif cmd == "backtest":
        run_once(backtest_mode=True)

    else:
        _usage()
        sys.exit(1)
