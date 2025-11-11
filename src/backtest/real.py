# src/backtest/real.py
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from src.backtest.loader import load_runs

try:
    from src.data.binance_client import get_ohlcv
except Exception:
    get_ohlcv = None  # type: ignore


def _build_levels(side: str, entry_price: float) -> Tuple[float, float]:
    # gleiche Logik wie im App-Code
    sl_pct = 0.004
    rr = 1.5
    if side == "LONG":
        sl = entry_price * (1.0 - sl_pct)
        tp = entry_price + (entry_price - sl) * rr
    else:
        sl = entry_price * (1.0 + sl_pct)
        tp = entry_price - (sl - entry_price) * rr
    return sl, tp


def _simulate(side: str, sl: float, tp: float, klines: List[List[Any]]) -> str:
    for k in klines:
        high = float(k[2])
        low = float(k[3])
        if side == "LONG":
            if high >= tp:
                return "TP"
            if low <= sl:
                return "SL"
        else:
            if low <= tp:
                return "TP"
            if high >= sl:
                return "SL"
    return "UNKNOWN"


def run_real_backtest(
    path: str = "data/runs.log",
    thr: float = 0.4,
    lookahead_bars: int = 24,
) -> Dict[str, Any]:
    """
    Schnellere Version:
    - lädt alle runs
    - filtert auf signals mit abs(score) >= thr und last_price vorhanden
    - gruppiert nach (pair, interval)
    - holt pro (pair, interval) genau EINEN OHLCV-Block und nutzt ihn für alle Trades dieses Pairs
    """
    runs = load_runs(path)

    # 1) relevante trades aus den logs extrahieren
    trades_raw: List[Dict[str, Any]] = []
    for run in runs:
        t = run.get("run_at")
        for res in run.get("results", []):
            score = float(res.get("score", 0.0))
            if abs(score) < thr:
                continue
            entry_price = res.get("last_price")
            if entry_price is None:
                continue
            decision = (res.get("decision") or "HOLD").upper()
            if decision in ("LONG", "SHORT"):
                side = decision
            else:
                side = "LONG" if score > 0 else "SHORT"

            trades_raw.append(
                {
                    "t": t,
                    "pair": res.get("pair"),
                    "interval": res.get("interval") or "15m",
                    "side": side,
                    "entry": float(entry_price),
                }
            )

    # 2) nach pair+interval gruppieren
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for tr in trades_raw:
        key = (tr["pair"], tr["interval"])
        groups.setdefault(key, []).append(tr)

    # 3) pro gruppe genau eine OHLCV holen
    results: List[Dict[str, Any]] = []
    for (pair, interval), trs in groups.items():
        klines: List[List[Any]] = []
        if get_ohlcv is not None:
            try:
                klines = get_ohlcv(pair, interval, limit=lookahead_bars)
            except Exception:
                klines = []
        # 4) alle trades dieser gruppe simulieren
        for tr in trs:
            sl, tp = _build_levels(tr["side"], tr["entry"])
            outcome = _simulate(tr["side"], sl, tp, klines)
            results.append(
                {
                    "t": tr["t"],
                    "pair": pair,
                    "interval": interval,
                    "side": tr["side"],
                    "entry": tr["entry"],
                    "stop_loss": sl,
                    "take_profit": tp,
                    "outcome": outcome,
                }
            )

    wins = sum(1 for r in results if r["outcome"] == "TP")
    losses = sum(1 for r in results if r["outcome"] == "SL")
    unknown = sum(1 for r in results if r["outcome"] not in ("TP", "SL"))

    return {
        "n_signals": sum(len(run.get("results", [])) for run in runs),
        "n_trades": len(results),
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "trades": results,
    }
