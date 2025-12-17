# src/app/main.py
from __future__ import annotations

# BOOTSTRAP ENV – EINMAL
from src.bootstrap.env import env_debug  # noqa: F401

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime, timezone

from src.tools.log_rotation import maybe_rotate_all_logs


# -------------------------------------------------------------------
# Trading & Environment Configuration
# -------------------------------------------------------------------

ENVIRONMENT = os.getenv("ENVIRONMENT", "paper").lower()
if ENVIRONMENT not in ("paper", "testnet", "live"):
    print(f"[WARN] Invalid ENVIRONMENT={ENVIRONMENT}, fallback to 'paper'", file=sys.stderr)
    ENVIRONMENT = "paper"

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
TRADING_HARD_STOP = os.getenv("TRADING_HARD_STOP", "false").lower() == "true"

MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "0"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "0"))
MAX_DAILY_RISK_R = float(os.getenv("MAX_DAILY_RISK_R", "0.0"))
MAX_RISK_PER_TRADE_R = float(os.getenv("MAX_RISK_PER_TRADE_R", "1.0"))
FINAL_SCORE_MIN = float(os.getenv("FINAL_SCORE_MIN", "0.6"))

# -------------------------------------------------------------------
# Paths & Defaults
# -------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"

DEFAULT_UNIVERSE = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT"]
DEFAULT_INTERVAL = "15m"
DEFAULT_MAX_AGE_SEC = 900

# Defaults nur als Fallback; eigentliche Werte kommen aus configs/weights.yaml & thresholds.yaml
DEFAULT_WEIGHTS = {
    "technical": 0.60,
}

DEFAULT_THRESHOLDS = {
    "long": 0.6,
    "short": -0.6,
}

# Trendfilter: wie stark muss Technical sein, um LONG/SHORT zu erlauben?
MIN_TREND_SCORE = float(os.getenv("MIN_TREND_SCORE", "0.2"))

# Agents
try:
    from src.agents.technical import TechnicalAgent
except Exception as e:
    print(f"[WARN] import TechnicalAgent failed: {e}", file=sys.stderr)
    TechnicalAgent = None


def load_all_agents():
    """
    Lädt alle produktiven Agents in der gewünschten Reihenfolge.

    Reihenfolge:
    - Technical (Driver)

    Falls ein Agent nicht importiert werden konnte:
    → wird er übersprungen.
    """
    agents = []

    if TechnicalAgent is not None:
        agents.append(TechnicalAgent())

    return agents

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
    from src.trade.limits import (  # type: ignore
        check_trading_limits,
        update_trading_state_after_trade,
    )
    PAPER_ENABLED = True
except Exception as e:
    print(f"[WARN] paper trading unavailable: {e}", file=sys.stderr)
    PAPER_ENABLED = False

# live dry-run logging (optional)
try:
    from src.trade.live_dry_run import log_live_dry_run_trade  # type: ignore
    LIVE_DRY_RUN_ENABLED = True
except Exception as e:
    print(f"[WARN] live dry-run logging unavailable: {e}", file=sys.stderr)
    LIVE_DRY_RUN_ENABLED = False

# close paper + mirror to testnet
try:
    from src.trade.close_paper_trades import main as close_paper_trades_main  # type: ignore
except Exception as e:
    print(f"[WARN] close_paper_trades unavailable: {e}", file=sys.stderr)
    close_paper_trades_main = None  # type: ignore

# binance spot testnet trading (optional)
try:
    from src.exchange.binance_spot_testnet import BinanceSpotTestnetClient  # type: ignore

    BINANCE_TESTNET_ENABLED = os.getenv("BINANCE_TESTNET_ENABLED", "false").lower() == "true"
    BINANCE_TESTNET_ORDER_QTY = float(os.getenv("BINANCE_TESTNET_ORDER_QTY", "0.001"))

    if BINANCE_TESTNET_ENABLED:
        try:
            BINANCE_TESTNET_CLIENT = BinanceSpotTestnetClient.from_env()
        except Exception as e:  # z. B. fehlende Keys
            print(f"[WARN] Binance Spot Testnet init failed: {e}", file=sys.stderr)
            BINANCE_TESTNET_CLIENT = None
    else:
        BINANCE_TESTNET_CLIENT = None
except Exception as e:
    print(f"[WARN] Binance Spot Testnet imports failed: {e}", file=sys.stderr)
    BINANCE_TESTNET_ENABLED = False
    BINANCE_TESTNET_CLIENT = None
    BINANCE_TESTNET_ORDER_QTY = 0.0

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
    """
    Konsens-Schwellen:
    - primär aus ENV: CONSENSUS_LONG / CONSENSUS_SHORT
    - sonst aus configs/thresholds.yaml
    - sonst DEFAULT_THRESHOLDS (0.6 / -0.6)
    """
    # 1) ENV versuchen
    env_long = os.getenv("CONSENSUS_LONG")
    env_short = os.getenv("CONSENSUS_SHORT")
    if env_long is not None and env_short is not None:
        try:
            return {
                "long": float(env_long),
                "short": float(env_short),
            }
        except ValueError:
            pass  # Fallback auf YAML/Defaults

    # 2) YAML-Fallback
    data = _read_yaml(CONFIG_DIR / "thresholds.yaml") or {}
    cons = data.get("consensus") or data
    long_val = cons.get("long")
    short_val = cons.get("short")

    try:
        long_thr = float(long_val) if long_val is not None else DEFAULT_THRESHOLDS["long"]
    except ValueError:
        long_thr = DEFAULT_THRESHOLDS["long"]

    try:
        short_thr = float(short_val) if short_val is not None else DEFAULT_THRESHOLDS["short"]
    except ValueError:
        short_thr = DEFAULT_THRESHOLDS["short"]

    return {"long": long_thr, "short": short_thr}


def load_telegram_score_min() -> float:
    """
    Basis-Schwelle für Telegram-Alerts.
    Default:
    - TELEGRAM_SCORE_MIN, falls gesetzt
    - sonst FINAL_SCORE_MIN
    """
    base = FINAL_SCORE_MIN
    raw = os.getenv("TELEGRAM_SCORE_MIN")
    if raw is None:
        return base
    try:
        return float(raw)
    except ValueError:
        return base


def load_testnet_score_min() -> float:
    """
    Score-Schwelle für Testnet-Orders.

    Default:
    - TESTNET_SCORE_MIN
    - sonst TELEGRAM_SCORE_MIN
    - sonst FINAL_SCORE_MIN
    """
    # 1) TESTNET_SCORE_MIN
    raw = os.getenv("TESTNET_SCORE_MIN")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass

    # 2) TELEGRAM_SCORE_MIN
    raw_tel = os.getenv("TELEGRAM_SCORE_MIN")
    if raw_tel is not None:
        try:
            return float(raw_tel)
        except ValueError:
            pass

    # 3) Fallback: FINAL_SCORE_MIN
    return FINAL_SCORE_MIN


def load_live_score_min() -> float:
    """
    Score-Schwelle für spätere Live-Orders.

    Default:
    - LIVE_SCORE_MIN
    - sonst TESTNET_SCORE_MIN
    - sonst TELEGRAM_SCORE_MIN
    - sonst FINAL_SCORE_MIN
    """
    for key in ("LIVE_SCORE_MIN", "TESTNET_SCORE_MIN", "TELEGRAM_SCORE_MIN"):
        raw = os.getenv(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return FINAL_SCORE_MIN


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


def _normalize_votes(raw_votes):
    """
    Normalisiert unterschiedliche Darstellungen von Agent-Votes
    in ein einheitliches Dict:
        { name: (score, conf, fresh), ... }

    Unterstützt:
    - dict(name -> (score, conf, fresh))
    - list[(name, score, conf, fresh), ...]
    - list[{"name"/"agent", "score", "confidence", "inputs_fresh"}, ...]
    """
    if isinstance(raw_votes, dict):
        return raw_votes

    votes_dict = {}
    if isinstance(raw_votes, list):
        for item in raw_votes:
            # Variante: Dict je Agent
            if isinstance(item, dict):
                name = item.get("name") or item.get("agent")
                score = float(item.get("score", 0.0))
                conf = float(item.get("confidence", 0.0))
                fresh = bool(item.get("inputs_fresh", True))
            # Variante: Tupel/Liste (name, score, conf, fresh)
            elif isinstance(item, (list, tuple)) and len(item) >= 4:
                name = str(item[0])
                score = float(item[1])
                conf = float(item[2])
                fresh = bool(item[3])
            else:
                continue

            if not name:
                continue
            votes_dict[str(name)] = (score, conf, fresh)

    return votes_dict


def decide_pair(
    pair: str,
    votes,
    weights: Dict[str, float],
    thresholds: Dict[str, float],
) -> Tuple[float, str, str, List[Tuple[str, float, float]]]:
    """
    Zweistufige Logik:
    1) Technical-Agent ist Driver und schlägt LONG/SHORT vor.
    2) Andere Agenten (News, Sentiment, Research) haben Veto-Recht,
       wenn sie mit hoher Confidence stark dagegenlaufen.
    3) Consensus-Score S wird weiterhin für Logging/Telegram/Backtests genutzt.

    Neu:
    - Nur „kritische“ Agenten (default: technical) blocken bei stale inputs.
    - Optionale Agenten (news, sentiment, research) werden bei stale ignoriert,
      blocken aber keine Trades mehr.
    """

    votes_dict = _normalize_votes(votes)
    if not votes_dict:
        return 0.0, "HOLD", "no votes", []

    # Kritische Agenten aus ENV (z.B. "technical" oder "technical,news")
    critical_raw = os.getenv("CRITICAL_AGENTS", "technical")
    critical_agents = {name.strip() for name in critical_raw.split(",") if name.strip()}
    if not critical_agents:
        critical_agents = {"technical"}

    breakdown: List[Tuple[str, float, float]] = []
    weighted_sum = 0.0
    total_weight = 0.0
    critical_stale: List[str] = []

    for name, (score, conf, fresh) in votes_dict.items():
        breakdown.append((name, score, conf))

        # Kritische Agenten stale -> merken, aber noch nicht sofort returnen
        if not fresh and name in critical_agents:
            critical_stale.append(name)
            continue

        # Optionale Agenten stale -> werden einfach ignoriert (kein Blocker)
        if not fresh:
            continue

        if conf <= 0.0:
            continue

        w = float(weights.get(name, 0.0))
        eff_w = w * conf
        weighted_sum += score * eff_w
        total_weight += eff_w

    if total_weight <= 0.0:
        S = 0.0
    else:
        S = max(-1.0, min(1.0, weighted_sum / total_weight))

    # Wenn kritische Agenten stale sind -> HOLD mit klarer Reason
    if critical_stale:
        reason = "critical stale: " + ",".join(sorted(set(critical_stale)))
        return S, "HOLD", reason, breakdown

    # 1) Technical als Driver
    tech = votes_dict.get("technical")
    if tech is None:
        return S, "HOLD", "no technical agent", breakdown

    tech_score, tech_conf, tech_fresh = tech
    if not tech_fresh:
        # redundanter Schutz, falls technical NICHT in CRITICAL_AGENTS gesetzt wäre
        return S, "HOLD", "critical stale: technical", breakdown

    tech_long_thr = float(os.getenv("TECH_DRIVER_LONG", "0.7"))
    tech_short_thr = float(os.getenv("TECH_DRIVER_SHORT", "-0.6"))

    proposed: Optional[str] = None
    if tech_score >= tech_long_thr:
        proposed = "LONG"
    elif tech_score <= tech_short_thr:
        proposed = "SHORT"

    if proposed is None:
        return S, "HOLD", "no technical edge", breakdown

    # 2) Veto-Logik: andere Agenten können Trade blocken (nur wenn frisch + stark)
    veto_score_min = float(os.getenv("TECH_VETO_SCORE_MIN", "0.5"))
    veto_conf_min = float(os.getenv("TECH_VETO_CONF_MIN", "0.5"))

    veto_agents: List[str] = []
    for name, (score, conf, fresh) in votes_dict.items():
        if name == "technical":
            continue
        if not fresh:
            # stale optionale Agenten veto-en NICHT
            continue
        if conf < veto_conf_min:
            continue
        if abs(score) < veto_score_min:
            continue

        if proposed == "LONG" and score < 0.0:
            veto_agents.append(name)
        elif proposed == "SHORT" and score > 0.0:
            veto_agents.append(name)

    if veto_agents:
        reason = "veto by " + ",".join(sorted(set(veto_agents)))
        return S, "HOLD", reason, breakdown

    # 3) Kein Veto: Trade wird akzeptiert, Technical ist Driver
    decision = proposed
    reason = "technical driver, no veto"
    return S, decision, reason, breakdown


def collect_votes(
    universe: List[str],
    interval: str,
    asof: datetime,
    max_age_sec: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """
    Vereinheitlichte Multi-Agent Vote Collection v2.

    - TechnicalAgent wird wie bisher per Pair und Candles aufgerufen.
    - AI Agents (News/Sentiment/Research) laufen universe-wide.
    - Jeder Agent liefert:
        {
            "pair": str,
            "agent": str,
            "score": float,
            "confidence": float,
            "inputs_fresh": bool,
            ...
        }
    """

    votes: List[Dict[str, Any]] = []
    last_prices: Dict[str, float] = {}

    # -------------------------------------------------
    # technische OHLCV-Daten laden
    # -------------------------------------------------
    eff_max_age_sec = _effective_freshness_sec(max_age_sec, interval)

    ohlcv_rows: Dict[str, Any] = {}
    candles_map: Dict[str, List[dict]] = {}
    fresh_map: Dict[str, bool] = {}

    for pair in universe:
        rows = _fetch_rows(pair, interval, 300)
        ohlcv_rows[pair] = rows

        if rows:
            ts = _latest_ts_from_rows(rows)
            fresh_map[pair] = _is_fresh(ts, eff_max_age_sec)
            last_close = _latest_close_from_rows(rows)
            if last_close is not None:
                last_prices[pair] = last_close

            candles = _rows_to_tech_candles(rows)
            if candles:
                candles_map[pair] = candles

    # -------------------------------------------------
    # Agents laden
    # -------------------------------------------------
    agent_objects = load_all_agents()

    # -------------------------------------------------
    # Agent-Execution
    # -------------------------------------------------
    for agent in agent_objects:

        name = agent.__class__.__name__

        # -------------------------------
        # TechnicalAgent (per Pair)
        # -------------------------------
        if name.lower().startswith("technical"):
            for pair in universe:
                candles = candles_map.get(pair)
                if not candles:
                    continue

                inputs_fresh = fresh_map.get(pair, False)

                try:
                    out = agent.run(pair, candles, inputs_fresh)
                except Exception as e:
                    print(f"[WARN] {name}.run failed for {pair}: {e}", file=sys.stderr)
                    continue

                if not isinstance(out, dict):
                    continue

                out.setdefault("agent", "technical")
                out.setdefault("pair", pair)
                out.setdefault("inputs_fresh", inputs_fresh)
                votes.append(out)

        # -------------------------------
        # AI-Agents (universe wide)
        # run(universe, asof)
        # -------------------------------
        else:
            try:
                agent_output = agent.run(universe, asof)
            except Exception as e:
                print(f"[WARN] {name}.run failed: {e}", file=sys.stderr)
                continue

            if not agent_output:
                continue

            # ai_agents liefern Liste je Pair
            for out in agent_output:
                if not isinstance(out, dict):
                    continue

                out.setdefault("agent", agent.agent_name)
                out.setdefault("inputs_fresh", True)
                votes.append(out)

    return votes, last_prices


def run_once(single_pair: str | None = None,
             override_price: float | None = None,
             backtest_mode: bool = False):
    asof = datetime.now(timezone.utc)

    # -----------------------------------------------
    # Log-Rotation (nur Logs, keine Backtest-Files)
    # -----------------------------------------------
    maybe_rotate_all_logs()

    pairs, interval, max_age_sec = load_universe()
    if single_pair is not None:
        pairs = [single_pair]
    base_weights = load_weights()
    thresholds = load_thresholds()
    telegram_score_min = load_telegram_score_min()
    testnet_score_min = load_testnet_score_min()
    live_score_min = load_live_score_min()


    # -----------------------------------------------
    # Realtime-Exit: offene Paper-/Testnet-Trades schließen
    # -----------------------------------------------
    if close_paper_trades_main is not None:
        try:
            close_paper_trades_main()
        except Exception as e:
            print(f"[WARN] close_paper_trades_main failed: {e}", file=sys.stderr)

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

    for res in results:
        if res["decision"] not in ("LONG", "SHORT"):
            continue

        # -------------------------------------------------
        # SCORE-GATE (Trade-Filter based on v3 analysis)
        # -------------------------------------------------
        score = res["score"]
        score_abs = abs(score)

        # Zulässige Score-Zone:
        # Trade nur bei |score| >= FINAL_SCORE_MIN
        allow_trade = (score_abs >= FINAL_SCORE_MIN)

        # --- Score-Gate: Logging für Backtest & Paper & Live ---
        try:
            with (DATA_DIR / "score_gate.log").open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "t": asof.isoformat(),
                    "pair": res["pair"],
                    "score": score,
                    "score_abs": score_abs,
                    "decision": res["decision"],
                    "reason": res["reason"],
                    "breakdown": res["breakdown"],
                    "interval": interval,
                    "allow_trade": allow_trade,
                    "backtest_mode": backtest_mode,
                }) + "\n")
        except Exception as e:
            print(f"[WARN] failed writing score_gate.log: {e}", file=sys.stderr)

        if not allow_trade:
            # HARD FILTER: keine Papiertrades, keine Orders, keine Telegram Alerts
            continue


        # -------------------------------------------------
        # Original-Code
        # -------------------------------------------------
        order_levels = None
        price = override_price if (backtest_mode and override_price is not None) else res.get("last_price")


        # -------------------------------------------------
        # Order-Levels berechnen
        # -------------------------------------------------
        if price is not None:
            order_levels = compute_order_levels(
                side=res["decision"],
                price=price,
                risk_pct=0.01,
                rr=1.5,
                sl_distance_pct=0.004,
            )

        # -------------------------------------------------
        # RISK-GATE (für echte Orders)
        # -------------------------------------------------
        can_trade = True
        risk_reason = ""

        # Hard Stop
        if TRADING_HARD_STOP:
            can_trade = False
            risk_reason = "TRADING_HARD_STOP active"

        # Mindest-Score für echte Orders
        if can_trade and score_abs < FINAL_SCORE_MIN:
            can_trade = False
            risk_reason = (
                f"score {res['score']:.3f} < FINAL_SCORE_MIN {FINAL_SCORE_MIN:.3f}"
            )

        # Tages-Limits
        if can_trade:
            ok_limits, reason = check_trading_limits(
                max_trades_per_day=MAX_TRADES_PER_DAY,
                max_daily_risk_r=MAX_DAILY_RISK_R,
                max_risk_per_trade_r=MAX_RISK_PER_TRADE_R,
                assumed_r_per_trade=1.0,
            )
            if not ok_limits:
                can_trade = False
                risk_reason = reason

        # BACKTEST: kein Paper-Trading, keine Orders, keine Trades speichern
        if backtest_mode:
            continue

        # -------------------------------------------------
        # PAPER TRADES (immer erlaubt)
        # -------------------------------------------------
        if (
            PAPER_ENABLED 
            and price is not None 
            and order_levels is not None
            and score_abs >= FINAL_SCORE_MIN
        ):

            # --- Score & Agent-Outputs erfassen ---
            entry_ts = asof.isoformat()
            entry_score = res["score"]

            # breakdown → agent_outputs (saubere Struktur)
            agent_outputs = {}
            for name, score, conf in res["breakdown"]:
                agent_outputs[name] = {
                    "score": score,
                    "confidence": conf,
                }

            open_paper_trade(
                pair=res["pair"],
                side=order_levels["side"],
                entry=order_levels["entry"],
                stop_loss=order_levels["stop_loss"],
                take_profit=order_levels["take_profit"],
                size=1.0,
                meta={
                    "entry_ts": entry_ts,
                    "entry_score": entry_score,
                    "agent_outputs": agent_outputs,
                    "decision": res["decision"],
                    "reason": res["reason"],
                    "breakdown": res["breakdown"],
                },
            )

        # -------------------------------------------------
        # LIVE DRY-RUN (ENVIRONMENT=live + DRY_RUN=true)
        # -------------------------------------------------
        if (
            can_trade
            and score_abs >= live_score_min
            and ENVIRONMENT == "live"
            and DRY_RUN
            and price is not None
            and order_levels is not None
        ):
            log_live_dry_run_trade(
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
                    "interval": interval,
                    "env": ENVIRONMENT,
                    "score_abs": score_abs,
                    "risk_reason": risk_reason,
                },
            )

        # -------------------------------------------------
        # TESTNET ORDERS (nur ein Block!)
        # -------------------------------------------------
        if (
            can_trade
            and score_abs >= testnet_score_min
            and ENVIRONMENT == "testnet"
            and BINANCE_TESTNET_ENABLED
            and BINANCE_TESTNET_CLIENT is not None
            and price is not None
            and order_levels is not None
        ):
            try:
                BINANCE_TESTNET_CLIENT.create_market_order(
                    symbol=res["pair"],
                    side=order_levels["side"],
                    quantity=BINANCE_TESTNET_ORDER_QTY,
                )
                update_trading_state_after_trade(assumed_r_per_trade=1.0)
            except Exception as e:
                print(
                    f"[ERROR] Failed to send Binance testnet order for {res['pair']}: {e}",
                    file=sys.stderr,
                )

        # -------------------------------------------------
        # TELEGRAM (erst ab telegram_score_min)
        # -------------------------------------------------
        if (
            single_pair is None
            and format_signal_message
            and send_telegram
            and score_abs >= telegram_score_min
        ):
            msg = format_signal_message(
                res["pair"],
                res["decision"],
                res["score"],
                res["breakdown"],
                res["reason"],
                order_levels=order_levels,
            )
            if risk_reason:
                msg += f"\n[RiskGate] {risk_reason}"
            send_telegram(msg)
    return results

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
