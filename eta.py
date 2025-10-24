import math, os, sqlite3
from pathlib import Path
import pandas as pd

def _median_or_none(x):
    return float(pd.Series(x).median()) if len(x) else None

def _hist_estimate_bars(s: dict, db_path: str) -> int | None:
    """Estimate bars-to-exit from historical results for same coin+side."""
    if not os.path.exists(db_path):
        return None
    con = sqlite3.connect(db_path)
    try:
        q = """
        SELECT outcome, bars_to_outcome
        FROM results
        WHERE coin_id = ? AND signal = ?
          AND bars_to_outcome IS NOT NULL
          AND outcome IN ('target','stop')
        ORDER BY evaluated_at DESC
        LIMIT 500
        """
        df = pd.read_sql_query(q, con, params=[s["coin_id"], s["signal"]])
        if df.empty or len(df) < 20:
            return None
        tgt = df[df.outcome == "target"]["bars_to_outcome"].tolist()
        stp = df[df.outcome == "stop"]["bars_to_outcome"].tolist()
        m_tgt = _median_or_none(tgt)
        m_stp = _median_or_none(stp)
        p_tgt = len(tgt) / len(df)
        p_stp = 1.0 - p_tgt
        if m_tgt is None and m_stp is None:
            return None
        # expected time-to-first-hit (weighted median proxy)
        exp_bars = 0.0
        if m_tgt is not None:
            exp_bars += p_tgt * m_tgt
        if m_stp is not None:
            exp_bars += p_stp * m_stp
        return int(max(1, round(exp_bars)))
    finally:
        con.close()

def estimate_bars(s: dict, bar_minutes: int, max_hold_bars: int, db_path: str = "data/signals.db") -> int:
    """
    Return estimated bars to exit (target or stop).
    1) Use historical results for this coin+side if available.
    2) Fallback: ATR/momentum-based.
    """
    # 1) History-driven
    est = _hist_estimate_bars(s, db_path)
    if est is not None:
        return min(max(1, est), max_hold_bars)

    # 2) Fallback heuristic with momentum multiplier
    price = float(s["price"])
    target = float(s["target"])
    ema = float(s["ema200"]) if float(s["ema200"]) != 0 else price
    atr = max(float(s["atr14"]), 1e-9)
    rsi = float(s["rsi14"])
    side = s["signal"]

    dist = abs(target - price)
    base = dist / atr  # bars at current volatility

    strong_momentum = (side == "LONG" and price > ema and rsi >= 55) or (side == "SHORT" and price < ema and rsi <= 45)
    weak_momentum   = (side == "LONG" and price < ema) or (side == "SHORT" and price > ema)

    k = 0.85 if strong_momentum else (1.15 if weak_momentum else 1.0)
    est_bars = int(math.ceil(base * k))
    return min(max(1, est_bars), max_hold_bars)
