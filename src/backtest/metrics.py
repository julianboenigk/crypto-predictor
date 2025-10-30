from __future__ import annotations
from dataclasses import dataclass
import math
from typing import List, Tuple

@dataclass(frozen=True)
class EquityPoint:
    t: int
    equity: float

@dataclass(frozen=True)
class Trade:
    entry_time: int
    entry_price: float
    direction: str  # "LONG" or "SHORT"
    size: float
    tp: float
    sl: float
    exit_time: int
    exit_price: float
    pnl: float  # in %
    r_multiple: float

def max_drawdown(equity_curve: List[EquityPoint]) -> float:
    peak = -math.inf
    mdd = 0.0
    for p in equity_curve:
        peak = max(peak, p.equity)
        dd = (peak - p.equity) / peak if peak > 0 else 0.0
        mdd = max(mdd, dd)
    return mdd

def sharpe(returns_pct: List[float], periods_per_year: int) -> float:
    if not returns_pct:
        return 0.0
    mean = sum(returns_pct) / len(returns_pct)
    var = sum((x - mean) ** 2 for x in returns_pct) / max(1, len(returns_pct) - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (mean / 100.0) * math.sqrt(periods_per_year) / (sd / 100.0)

def summarize(trades: List[Trade], eq: List[EquityPoint]) -> dict:
    wins = [t for t in trades if t.pnl > 0]
    losses = [t for t in trades if t.pnl <= 0]
    avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0
    winrate = len(wins) / len(trades) if trades else 0.0
    expectancy = winrate * avg_win + (1 - winrate) * avg_loss
    dd = max_drawdown(eq)
    ret_series = []
    for i in range(1, len(eq)):
        prev = eq[i-1].equity
        cur = eq[i].equity
        ret_series.append((cur - prev) / prev * 100.0)
    # 15m bars ~ 4 * 24 * 365 = 35040 per year (approx)
    sr = sharpe(ret_series, periods_per_year=35040)
    return {
        "trades": len(trades),
        "winrate_pct": round(winrate * 100, 2),
        "avg_win_pct": round(avg_win, 3),
        "avg_loss_pct": round(avg_loss, 3),
        "expectancy_pct": round(expectancy, 3),
        "max_drawdown_pct": round(dd * 100, 2),
        "sharpe": round(sr, 2),
        "equity_final_pct": round((eq[-1].equity - eq[0].equity) / eq[0].equity * 100.0, 2) if eq else 0.0,
    }
