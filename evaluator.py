import os, sqlite3, time, math
from datetime import datetime, timezone
import requests
import pandas as pd
import config

BINANCE = "https://api.binance.com"
DB_PATH = os.path.join(config.DATA_DIR, "signals.db")

# how many future bars to watch (1h bars → 48 = 2 days)
HORIZON_BARS = 48

def _get(path, params):
    r = requests.get(f"{BINANCE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r

def _klines(symbol: str, interval: str, start_ms: int, limit: int):
    r = _get("/api/v3/klines", {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "limit": limit
    })
    cols = ["t","o","h","l","c","v","ct","qv","n","tb","tqv","ig"]
    df = pd.DataFrame(r.json(), columns=cols)
    if df.empty: return df
    df = df[["t","o","h","l","c"]].astype({"o":"float64","h":"float64","l":"float64","c":"float64"})
    return df

def _ensure_results_table(cur):
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results(
      ts TEXT, coin_id TEXT, signal TEXT,
      price REAL, stop REAL, target REAL, rr REAL,
      ema200 REAL, rsi14 REAL, atr14 REAL,
      outcome TEXT, r_realized REAL, pnl_pct REAL,
      bars_to_outcome INTEGER, evaluated_at TEXT
    )
    """)

def _already_evaluated(cur, ts, coin_id, signal):
    cur.execute("SELECT 1 FROM results WHERE ts=? AND coin_id=? AND signal=? LIMIT 1",
                (ts, coin_id, signal))
    return cur.fetchone() is not None

def _first_touch(side, future: pd.DataFrame, stop: float, target: float):
    # return ("target"/"stop"/"timeout", bars_to_outcome, exit_price)
    for i, row in enumerate(future.itertuples(index=False), start=1):
        high, low = row.h, row.l
        if side == "LONG":
            hit_target = high >= target
            hit_stop   = low  <= stop
            if hit_target and hit_stop:
                # conservative: whichever is closer to open -> choose first likely touch; assume stop first if open below mid
                return ("stop", i, stop) if abs(row.o - stop) < abs(row.o - target) else ("target", i, target)
            if hit_target: return ("target", i, target)
            if hit_stop:   return ("stop",   i, stop)
        else:
            hit_target = low  <= target
            hit_stop   = high >= stop
            if hit_target and hit_stop:
                return ("stop", i, stop) if abs(row.o - stop) < abs(row.o - target) else ("target", i, target)
            if hit_target: return ("target", i, target)
            if hit_stop:   return ("stop",   i, stop)
    return ("timeout", len(future), future.c.iloc[-1] if len(future) else None)

def evaluate_once():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    _ensure_results_table(cur)

    sigs = pd.read_sql_query("SELECT * FROM signals ORDER BY ts DESC", conn)
    if sigs.empty:
        print("no signals to evaluate"); conn.close(); return

    evaluated = 0
    for row in sigs.itertuples(index=False):
        ts_iso = row.ts
        coin_id = row.coin_id  # may already be a Binance symbol like WALUSDT
        side = row.signal
        if _already_evaluated(cur, ts_iso, coin_id, side): continue

        # symbol resolution
        symbol = config.SYMBOL_MAP.get(coin_id, coin_id)
        if not symbol.endswith("USDT"): continue

        # start from next bar
        # parse ts to ms
        dt = datetime.fromisoformat(ts_iso.replace("Z","+00:00")).astimezone(timezone.utc)
        start_ms = int(dt.timestamp()*1000) + 1

        fut = _klines(symbol, config.BINANCE_INTERVAL, start_ms, HORIZON_BARS)
        outcome, bars, exit_px = _first_touch(side, fut, row.stop, row.target)

        price = row.price
        if side == "LONG":
            risk = price - row.stop
            r_realized = (exit_px - price)/risk if risk>0 and exit_px else 0.0
            pnl_pct = (exit_px/price - 1)*100 if exit_px else 0.0
        else:
            risk = row.stop - price
            r_realized = (price - exit_px)/risk if risk>0 and exit_px else 0.0
            pnl_pct = (1 - exit_px/price)*100 if exit_px else 0.0

        cur.execute("""INSERT INTO results
          (ts,coin_id,signal,price,stop,target,rr,ema200,rsi14,atr14,outcome,r_realized,pnl_pct,bars_to_outcome,evaluated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
        """, (ts_iso, coin_id, side, row.price, row.stop, row.target, row.rr,
              row.ema200, row.rsi14, row.atr14, outcome, round(r_realized,3),
              round(pnl_pct,3), int(bars)))
        evaluated += 1

    conn.commit()
    conn.close()
    print(f"evaluated {evaluated} signals")

if __name__ == "__main__":
    evaluate_once()
