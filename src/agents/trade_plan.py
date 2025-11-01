# src/agents/trade_plan.py
# -----------------------------------------------------------------------------
# Builds a concrete trade plan (entry, stop-loss, take-profits, validity window)
# from a consensus score and basic market metrics. The plan also carries a
# certainty percentage, which you can set from the caller after computing it.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Metrics:
    """Minimal inputs to derive a plan."""
    price: float              # current price
    ema200: float             # EMA-200 value (same timeframe as price)
    atr_pct: float            # ATR as percent of price (e.g., 0.25 means 0.25%)
    rsi14: Optional[float] = None  # optional, informational only


@dataclass
class Plan:
    """Concrete plan to act on."""
    pair: str
    action: Action
    entry_type: Literal["limit", "market"]
    entry: Optional[float]
    stop: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    valid_until: str          # ISO-8601 UTC timestamp
    note: str
    # Will be set by the caller after certainty calculation
    certainty_pct: float = 50.0


def _atr_abs(price: float, atr_pct: float) -> float:
    """Convert ATR% to absolute price distance."""
    return price * (atr_pct / 100.0)


def decide_action(score: float, price: float, ema200: float) -> Action:
    """
    Simple regime filter:
      • BUY  if score >= +0.25 and price >= ema200
      • SELL if score <= -0.25 and price <= ema200
      • otherwise HOLD
    """
    if score >= 0.25 and price >= ema200:
        return "BUY"
    if score <= -0.25 and price <= ema200:
        return "SELL"
    return "HOLD"


def build_plan(
    pair: str,
    score: float,
    m: Metrics,
    now: Optional[datetime] = None,
) -> Plan:
    """
    Create a Plan from consensus score and metrics.

    Rules:
      • HOLD → no entry/stop/targets; valid for 60 min; guidance-only note.
      • BUY/SELL → limit entry close to price/EMA with ATR-based buffers:
           - 'strong' if |score| >= 0.40 → wider stop (k=1.8)
           - else k=1.5
         TP1 = entry ± 1*ATR; TP2 = entry ± 2*ATR (directional).
      • entry_type = 'limit' if ATR > 0 (normal case) else 'market'.
    """
    now = now or datetime.now(timezone.utc)
    valid_until = (now + timedelta(minutes=60)).isoformat()

    action = decide_action(score, m.price, m.ema200)

    if action == "HOLD":
        return Plan(
            pair=pair,
            action="HOLD",
            entry_type="market",
            entry=None,
            stop=None,
            tp1=None,
            tp2=None,
            valid_until=valid_until,
            note="No strong edge. Re-evaluate next cycle.",
            certainty_pct=50.0,
        )

    atr = _atr_abs(m.price, m.atr_pct)
    strong = abs(score) >= 0.40
    k = 1.8 if strong else 1.5  # wider stop on stronger conviction

    if action == "BUY":
        # Slightly above the cheaper of (price, ema200) to avoid chasing spikes
        entry = min(m.price, m.ema200) + 0.10 * atr
        stop = entry - k * atr
        tp1 = entry + 1.0 * atr
        tp2 = entry + 2.0 * atr
        note = f"Uptrend bias. k={k}, ATR={atr:.6f}"
    else:  # SELL
        # Slightly below the more expensive of (price, ema200) to avoid shorting spikes
        entry = max(m.price, m.ema200) - 0.10 * atr
        stop = entry + k * atr
        tp1 = entry - 1.0 * atr
        tp2 = entry - 2.0 * atr
        note = f"Downtrend bias. k={k}, ATR={atr:.6f}"

    # Round to a sensible precision (6 decimal places safe for most pairs)
    entry = round(entry, 6)
    stop = round(stop, 6)
    tp1 = round(tp1, 6)
    tp2 = round(tp2, 6)

    entry_type = "limit" if atr > 0 else "market"

    return Plan(
        pair=pair,
        action=action,
        entry_type=entry_type,
        entry=entry,
        stop=stop,
        tp1=tp1,
        tp2=tp2,
        valid_until=valid_until,
        note=note,
        certainty_pct=50.0,  # set by caller after computing certainty
    )
