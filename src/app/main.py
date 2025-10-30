from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import yaml

# Agents
from src.agents.technical import TechnicalAgent
from src.agents.sentiment import SentimentAgent
from src.agents.news import NewsAgent
from src.agents.research import ResearchAgent

# Data fetch / freshness (best-effort; guarded if an implementation detail differs)
from src.data.binance_client import BinanceClient

# Notifications
from src.core.notifier import send_telegram, telegram_enabled

# Policy (M4)
from src.policy.filters import load_policy, gate_decision


# ----------------------------
# Types & small infrastructure
# ----------------------------

@dataclass(frozen=True)
class Vote:
    name: str
    score: float
    confidence: float
    info: Dict[str, Any]
    inputs_fresh: bool

    @staticmethod
    def from_result(name: str, res: Any) -> "Vote":
        """
        Adapts either a dict-like or object-like agent result into our Vote.
        Expected fields:
          - score: float in [-1, 1]
          - confidence: float in [0, 1]
          - explanation/info fields (optional)
          - inputs_fresh: bool
        """
        if isinstance(res, dict):
            score = float(res.get("score", 0.0))
            conf = float(res.get("confidence", 0.0))
            info: Dict[str, Any] = {}
            # Merge common keys into info, but avoid duplicating score/conf
            for k, v in res.items():
                if k not in ("score", "confidence"):
                    info[k] = v
            fresh = bool(res.get("inputs_fresh", True))
            return Vote(name=name, score=score, confidence=conf, info=info, inputs_fresh=fresh)

        # object-like with attributes
        score = float(getattr(res, "score", 0.0))
        conf = float(getattr(res, "confidence", 0.0))
        info_attr = getattr(res, "info", {}) or {}
        info = dict(info_attr) if isinstance(info_attr, dict) else {}
        fresh = bool(getattr(res, "inputs_fresh", True))
        return Vote(name=name, score=score, confidence=conf, info=info, inputs_fresh=fresh)


# ----------------------------
# Config helpers
# ----------------------------

def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_universe() -> Dict[str, Any]:
    cfg = _read_yaml(Path("configs/universe.yaml"))
    # expected keys: pairs: [BTCUSDT,...], interval: "15m", freshness_ms, data_dir, etc.
    return {
        "pairs": cfg.get("pairs", ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]),
        "interval": cfg.get("interval", "15m"),
        "freshness_ms": int(cfg.get("freshness_ms", 75 * 60 * 1000)),  # default 75 minutes
        "data_dir": cfg.get("data_dir", "data"),
    }


def _load_weights() -> Dict[str, float]:
    w = _read_yaml(Path("configs/weights.yaml"))
    # expected keys: technical, sentiment, news, research
    return {
        "technical": float(w.get("technical", 0.45)),
        "sentiment": float(w.get("sentiment", 0.20)),
        "news": float(w.get("news", 0.20)),
        "research": float(w.get("research", 0.15)),
    }


# ----------------------------
# Freshness / fetching
# ----------------------------

def _freshen_csv(client: BinanceClient, pair: str, interval: str, data_dir: str) -> None:
    """
    Attempts to append recent candles into CSV.
    Prints a [FRESH] line similar to your previous runs.
    Guarded against API or implementation differences.
    """
    try:
        out = client.ensure_csv_up_to_date(pair=pair, interval=interval, data_dir=data_dir)
        # expected: dict with rows_appended and file; we print best-effort
        rows_appended = out.get("rows_appended", out.get("appended", out.get("rows", 0)))
        file_path = out.get("file", f"{data_dir}/{pair}_{interval}.csv")
        print(f"[FRESH] {pair} rows_appended={rows_appended} file={file_path}")
    except AttributeError:
        # Fallback to older helper name
        try:
            rows_appended, file_path = client.append_latest_csv(pair=pair, interval=interval, data_dir=data_dir)
            print(f"[FRESH] {pair} rows_appended={rows_appended} file={file_path}")
        except Exception as e:
            print(f"[FRESH][WARN] {pair}: {e}")
    except Exception as e:
        print(f"[FRESH][WARN] {pair}: {e}")


# ----------------------------
# Consensus & decision
# ----------------------------

def _consensus(votes: Iterable[Vote], weights: Dict[str, float]) -> Tuple[float, Dict[str, float], bool]:
    """
    Returns (S, components, inputs_all_fresh)
      - S: weighted score
      - components: {name: contribution}
      - inputs_all_fresh: True if all votes.inputs_fresh == True
    """
    comps: Dict[str, float] = {}
    all_fresh = True
    S = 0.0
    for v in votes:
        w = float(weights.get(v.name, 0.0))
        contrib = v.score * w
        comps[v.name] = contrib
        S += contrib
        if not v.inputs_fresh:
            all_fresh = False
    return S, comps, all_fresh


def _side_from_S(S: float, pos_threshold: float = 0.4, neg_threshold: float = -0.4) -> str:
    if S >= pos_threshold:
        return "LONG"
    if S <= neg_threshold:
        return "SHORT"
    return "HOLD"


# ----------------------------
# DB logging
# ----------------------------

def _ensure_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            pair TEXT NOT NULL,
            side TEXT NOT NULL,
            score REAL NOT NULL,
            details TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _insert_signal(path: Path, ts: int, pair: str, side: str, score: float, details: Dict[str, Any]) -> None:
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO signals (ts, pair, side, score, details) VALUES (?, ?, ?, ?, ?)",
        (ts, pair, side, score, json.dumps(details)),
    )
    conn.commit()
    conn.close()


# ----------------------------
# Main run
# ----------------------------

def run_once() -> int:
    uni = _load_universe()
    weights = _load_weights()
    policy = load_policy()

    data_dir = uni["data_dir"]
    interval = uni["interval"]
    db_path = Path(data_dir) / "signals.db"
    _ensure_db(db_path)

    # init data client & agents
    client = BinanceClient()

    tech = TechnicalAgent()
    sent = SentimentAgent()
    news = NewsAgent()
    rsch = ResearchAgent()

    now_ms = int(time.time() * 1000)

    for pair in uni["pairs"]:
        # 1) Freshen data (best-effort)
        _freshen_csv(client, pair, interval, data_dir)

        # 2) Evaluate agents
        #    Agents read from their own sources/CSV/json; we adapt to Vote
        t0 = time.time()

        tech_res = tech.evaluate(pair=pair, interval=interval)
        v_tech = Vote.from_result("technical", tech_res)

        sent_res = sent.evaluate(pair=pair)
        v_sent = Vote.from_result("sentiment", sent_res)

        news_res = news.evaluate(pair=pair)
        v_news = Vote.from_result("news", news_res)

        rsch_res = rsch.evaluate(pair=pair, interval=interval)
        v_rsch = Vote.from_result("research", rsch_res)

        # 3) Print agent lines (matching your style)
        # TECH
        tp = v_tech.info
        price = tp.get("price")
        ema200 = tp.get("ema200")
        rsi14 = tp.get("rsi14")
        atr_pct = tp.get("atr_pct", tp.get("atr%"))
        trend = tp.get("trend")
        rsi_sig = tp.get("rsi_sig")
        print(
            f"[TECH] {pair} score={v_tech.score:+.2f} conf={v_tech.confidence:.2f} :: "
            f"price={price}, ema200={ema200}, rsi14={rsi14}, atr%={atr_pct}, trend={trend}, rsi_sig={rsi_sig}"
        )

        # SENT
        sp = v_sent.info
        pol = sp.get("pol")
        vz = sp.get("vz")
        sig = sp.get("sig")
        print(
            f"[SENT] {pair} score={v_sent.score:+.2f} conf={v_sent.confidence:.2f} :: "
            f"pol={pol}, vz={vz}, sig={sig}, ts_fresh={v_sent.inputs_fresh}"
        )

        # NEWS
        np = v_news.info
        bias = np.get("bias")
        novelty = np.get("novelty")
        amp = np.get("amp", 0.50)
        print(
            f"[NEWS] {pair} score={v_news.score:+.2f} conf={v_news.confidence:.2f} :: "
            f"bias={bias:+.2f}, novelty={novelty:.2f}, amp={amp:.2f}, ts_fresh={v_news.inputs_fresh}"
        )

        # RSCH
        rp = v_rsch.info
        ema200_slope_pct = rp.get("ema200_slope%")
        dd_pct = rp.get("dd%")
        trend_bias = rp.get("trend_bias")
        dd_penalty = rp.get("dd_penalty")
        print(
            f"[RSCH] {pair} score={v_rsch.score:+.2f} conf={v_rsch.confidence:.2f} :: "
            f"ema200_slope%={ema200_slope_pct}, dd%={dd_pct}, trend_bias={trend_bias}, dd_penalty={dd_penalty}"
        )

        # 4) Consensus
        votes = [v_tech, v_sent, v_news, v_rsch]
        S, comps, all_fresh = _consensus(votes, weights)
        side = _side_from_S(S, pos_threshold=0.4, neg_threshold=-0.4)

        comp_str = ", ".join(
            f"{name}={comps[name]:+0.2f}×w{weights.get(name, 0.0):.2f}" for name in ("technical", "sentiment", "news", "research")
            if name in comps
        )
        print(f"[CONSENSUS] {pair} {side} S={S:+.3f} :: S={S:+.3f} from {comp_str}")

        # 5) Policy gate (M4) — turn non-compliant LONG/SHORT into HOLD
        policy_ctx = {
            "atr_pct": atr_pct if isinstance(atr_pct, (int, float)) else 0.0,
            "inputs_fresh": all_fresh,
            # "rr_at_entry": optional if you estimate R:R at runtime
        }
        allowed, reason = gate_decision(side, S, policy_ctx, policy)
        final_side = side
        if side in ("LONG", "SHORT") and not allowed:
            final_side = "HOLD"
            print(f"[POLICY] {pair} HOLD by policy :: {reason}")

        # 6) Persist signal + (optional) Telegram
        details = {
            "S": S,
            "components": comps,
            "weights": weights,
            "votes": {
                "technical": {"score": v_tech.score, "confidence": v_tech.confidence, "info": v_tech.info, "fresh": v_tech.inputs_fresh},
                "sentiment": {"score": v_sent.score, "confidence": v_sent.confidence, "info": v_sent.info, "fresh": v_sent.inputs_fresh},
                "news": {"score": v_news.score, "confidence": v_news.confidence, "info": v_news.info, "fresh": v_news.inputs_fresh},
                "research": {"score": v_rsch.score, "confidence": v_rsch.confidence, "info": v_rsch.info, "fresh": v_rsch.inputs_fresh},
            },
            "policy": {
                "allowed": allowed,
                "reason": reason,
            },
            "latency_ms": int((time.time() - t0) * 1000),
        }

        _insert_signal(db_path, int(time.time()), pair, final_side, float(S), details)

        if final_side in ("LONG", "SHORT") and telegram_enabled():
            msg = (
                f"{'📈' if final_side == 'LONG' else '📉'} {final_side} {pair}\n"
                f"S={S:+.2f} (tech={v_tech.score:+.2f}, sent={v_sent.score:+.2f}, news={v_news.score:+.2f}, rsch={v_rsch.score:+.2f})\n"
                f"Policy: { 'ok' if allowed else reason }"
            )
            send_telegram(msg)

    return 0


# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Run the full pipeline once")
    _ = run_p  # keep for symmetry / future args

    args = ap.parse_args()
    cmd = args.cmd or "run"

    if cmd == "run":
        return run_once()

    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
