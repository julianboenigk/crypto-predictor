from __future__ import annotations
import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

from src.backtest.metrics import Trade, EquityPoint, summarize

# --- Minimal TA helpers (EMA, RSI, ATR) mirroring your tech agent ---
def ema(vals: List[float], period: int) -> List[Optional[float]]:
    k = 2 / (period + 1)
    out: List[Optional[float]] = [None] * len(vals)
    ema_val: Optional[float] = None
    for i, v in enumerate(vals):
        if ema_val is None:
            ema_val = v
        else:
            ema_val = v * k + ema_val * (1 - k)
        out[i] = ema_val
    return out

def rsi(close: List[float], period: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(close)
    gains, losses = 0.0, 0.0
    for i in range(1, len(close)):
        chg = close[i] - close[i - 1]
        gains += max(chg, 0)
        losses += max(-chg, 0)
        if i >= period:
            gains -= max(close[i - period + 1] - close[i - period], 0)
            losses -= max(close[i - period] - close[i - period + 1], 0)
            rs = (gains / period) / ((losses / period) + 1e-12)
            out[i] = 100 - (100 / (1 + rs))
    return out

def true_range(h: List[float], l: List[float], c: List[float]) -> List[float]:
    tr = [0.0] * len(c)
    for i in range(len(c)):
        if i == 0:
            tr[i] = h[i] - l[i]
        else:
            tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    return tr

def atr(h: List[float], l: List[float], c: List[float], period: int = 14) -> List[Optional[float]]:
    tr = true_range(h, l, c)
    out: List[Optional[float]] = [None] * len(c)
    s = 0.0
    for i, v in enumerate(tr):
        s = (s * (period - 1) + v) / period if i > 0 else v
        out[i] = s
    return out

# --- Policy config ---
@dataclass
class Policy:
    min_score_threshold: float = 0.4    # same as live
    max_atr_pct: float = 2.0            # skip trades if ATR% above this
    rr_min: float = 1.5                 # reward:risk at least 1.5
    use_stop_tp_atr_mult: Tuple[float, float] = (1.0, 1.5)  # SL, TP in ATR multiples

def _row_is_header_or_blank(row: List[str]) -> bool:
    if not row or all(cell.strip() == "" for cell in row):
        return True
    sample = "".join(row[:2])
    return not any(ch.isdigit() for ch in sample)  # crude: first cols must contain digits

def load_csv(path: Path) -> Tuple[List[int], List[float], List[float], List[float], List[float], List[float]]:
    ts: List[int] = []
    o: List[float] = []
    h: List[float] = []
    l: List[float] = []
    c: List[float] = []
    v: List[float] = []
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    with path.open() as f:
        r = csv.reader(f)
        for row in r:
            if _row_is_header_or_blank(row):
                continue
            try:
                # expected: time, open, high, low, close, volume (ms ts ok)
                t = int(float(row[0]))
                ts.append(t)
                o.append(float(row[1]))
                h.append(float(row[2]))
                l.append(float(row[3]))
                c.append(float(row[4]))
                v.append(float(row[5]))
            except (ValueError, IndexError):
                # skip malformed lines
                continue

    if not ts:
        raise ValueError(f"No candle rows parsed from CSV: {path}")
    return ts, o, h, l, c, v

def decide_tech_signal(price: float, ema200: Optional[float], rsi14: Optional[float], atrp: Optional[float]) -> Tuple[str, float]:
    if ema200 is None or rsi14 is None or atrp is None:
        return "HOLD", 0.0
    score = 0.0
    score += 0.3 if price > ema200 else -0.3
    if rsi14 < 30:
        score += 0.5
    elif rsi14 > 70:
        score -= 0.5
    return ("LONG" if score >= 0.4 else "SHORT" if score <= -0.4 else "HOLD", score)

def run_backtest(pair: str, csv_path: Path, policy: Policy, start_ts: Optional[int], end_ts: Optional[int]) -> dict:
    ts, o, h, l, c, v = load_csv(csv_path)

    # If date window cuts all data, give a clear message with file span.
    span_min, span_max = ts[0], ts[-1]
    if start_ts:
        idx0 = next((i for i, t in enumerate(ts) if t >= start_ts), len(ts))
    else:
        idx0 = 0
    if end_ts:
        idx1 = next((i for i, t in enumerate(ts) if t > end_ts), len(ts))
    else:
        idx1 = len(ts)

    ts = ts[idx0:idx1]
    o = o[idx0:idx1]
    h = h[idx0:idx1]
    l = l[idx0:idx1]
    c = c[idx0:idx1]
    v = v[idx0:idx1]

    if not ts:
        def _fmt(ms: int) -> str:
            import datetime as dt
            return dt.datetime.utcfromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M")
        raise SystemExit(
            f"[BACKTEST] No bars in selected range for {pair}.\n"
            f"  File span: { _fmt(span_min) } → { _fmt(span_max) } UTC\n"
            f"  You passed: start={start_ts} end={end_ts}\n"
            f"  Tip: re-run without --start/--end or choose dates within the span."
        )

    equity = 10000.0
    eq_curve = [EquityPoint(ts[0], equity)]
    trades: List[Trade] = []
    in_pos = False
    dirn = ""
    entry_price = 0.0
    sl = 0.0
    tp = 0.0
    risk_per_trade_pct = 1.0  # simple fixed % of equity “at risk”

    ema200 = ema(c, 200)
    rsi14 = rsi(c, 14)
    atr14 = atr(h, l, c, 14)

    for i in range(len(c)):
        if ema200[i] is None or rsi14[i] is None or atr14[i] is None:
            eq_curve.append(EquityPoint(ts[i], equity))
            continue

        atrp = atr14[i] / c[i] * 100.0
        if atrp > policy.max_atr_pct and not in_pos:
            eq_curve.append(EquityPoint(ts[i], equity))
            continue

        action, score = decide_tech_signal(c[i], ema200[i], rsi14[i], atrp)
        if not in_pos and action in ("LONG", "SHORT") and abs(score) >= policy.min_score_threshold:
            sl_mult, tp_mult = policy.use_stop_tp_atr_mult
            if action == "LONG":
                sl = c[i] - atr14[i] * sl_mult
                tp = c[i] + atr14[i] * tp_mult
            else:
                sl = c[i] + atr14[i] * sl_mult
                tp = c[i] - atr14[i] * tp_mult
            rr = abs((tp - c[i]) / (c[i] - sl)) if action == "LONG" else abs((c[i] - tp) / (sl - c[i]))
            if rr < policy.rr_min:
                eq_curve.append(EquityPoint(ts[i], equity))
                continue
            in_pos = True
            dirn = action
            entry_price = c[i]
        elif in_pos:
            if dirn == "LONG":
                hit_sl = l[i] <= sl
                hit_tp = h[i] >= tp
                exit_price = sl if hit_sl and not hit_tp else tp if hit_tp and not hit_sl else None
            else:
                hit_sl = h[i] >= sl
                hit_tp = l[i] <= tp
                exit_price = sl if hit_sl and not hit_tp else tp if hit_tp and not hit_sl else None
            if exit_price is not None:
                pnl_pct = (exit_price - entry_price) / entry_price * 100.0 if dirn == "LONG" else (entry_price - exit_price) / entry_price * 100.0
                risk_price = abs(entry_price - sl)
                size = (equity * (risk_per_trade_pct / 100.0)) / max(risk_price, 1e-9)
                equity *= (1 + (pnl_pct / 100.0) * (size * entry_price / equity))
                r_mult = abs(exit_price - entry_price) / max(abs(entry_price - sl), 1e-9)
                trades.append(Trade(
                    entry_time=ts[i], entry_price=entry_price, direction=dirn,
                    size=size, tp=tp, sl=sl, exit_time=ts[i], exit_price=exit_price,
                    pnl=pnl_pct, r_multiple=r_mult
                ))
                in_pos = False
                dirn = ""
                entry_price = 0.0
                sl = 0.0
                tp = 0.0

        eq_curve.append(EquityPoint(ts[i], equity))

    report = summarize(trades, eq_curve)
    report["pair"] = pair
    report["bars"] = len(c)
    return report

def parse_time(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    import datetime as dt
    t = dt.datetime.strptime(s, "%Y-%m-%d")
    return int(t.timestamp() * 1000)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, help="e.g. BTCUSDT")
    ap.add_argument("--csv", default=None, help="path to CSV (defaults to data/{PAIR}_15m.csv)")
    ap.add_argument("--start", default=None, help="YYYY-MM-DD (inclusive, UTC)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (exclusive, UTC)")
    ap.add_argument("--rr", type=float, default=1.5, help="min reward:risk")
    ap.add_argument("--atrmax", type=float, default=2.0, help="max ATR%% filter")
    ap.add_argument("--score", type=float, default=0.4, help="min tech score to enter")
    args = ap.parse_args()

    csv_path = Path(args.csv) if args.csv else Path(f"data/{args.pair}_15m.csv")
    pol = Policy(min_score_threshold=args.score, max_atr_pct=args.atrmax, rr_min=args.rr)

    rep = run_backtest(args.pair, csv_path, pol, parse_time(args.start), parse_time(args.end))
    print(f"[BACKTEST] {rep['pair']} bars={rep['bars']} trades={rep['trades']}")
    print(f"  winrate={rep['winrate_pct']}%  avg_win={rep['avg_win_pct']}%  avg_loss={rep['avg_loss_pct']}%")
    print(f"  expectancy={rep['expectancy_pct']}%  maxDD={rep['max_drawdown_pct']}%  sharpe={rep['sharpe']}")
    print(f"  equity_final={rep['equity_final_pct']}%")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
