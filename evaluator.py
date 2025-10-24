# evaluator.py
import os, sqlite3, requests, math
from datetime import datetime, timezone
import pandas as pd
import config

BINANCE = "https://api.binance.com"
DB_PATH = os.path.join(config.DATA_DIR, "signals.db")

# ── HTTP / data ────────────────────────────────────────────────────────────
def _get(path, params, timeout=30):
    r = requests.get(f"{BINANCE}{path}", params=params, timeout=timeout)
    r.raise_for_status()
    return r

def _symbol_for(coin_id: str) -> str:
    return coin_id if coin_id.endswith("USDT") else config.SYMBOL_MAP.get(coin_id, "")

def _klines(symbol: str, interval: str, start_ms: int, limit: int) -> pd.DataFrame:
    r = _get("/api/v3/klines", {
        "symbol": symbol, "interval": interval, "startTime": start_ms, "limit": limit
    })
    cols = ["t","o","h","l","c","v","ct","qv","n","tb","tqv","ig"]
    df = pd.DataFrame(r.json(), columns=cols)
    if df.empty: return df
    df = df[["t","o","h","l","c"]].astype({"o":"float64","h":"float64","l":"float64","c":"float64"})
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    return df

def _first_touch(side: str, fut: pd.DataFrame, price: float, stop: float, target: float):
    for i, row in enumerate(fut.itertuples(index=False), start=1):
        o, h, l, tts = row.o, row.h, row.l, row.t
        if side == "LONG":
            hit_t, hit_s = (h >= target), (l <= stop)
        else:
            hit_t, hit_s = (l <= target), (h >= stop)
        if hit_t and hit_s:
            return ("target", i, target, tts.isoformat()+"Z") if abs(o-target) <= abs(o-stop) \
                   else ("stop", i, stop, tts.isoformat()+"Z")
        if hit_t: return ("target", i, target, tts.isoformat()+"Z")
        if hit_s: return ("stop",   i, stop,   tts.isoformat()+"Z")
    if len(fut):
        last = fut.iloc[-1]
        return ("timeout", len(fut), float(last.c), last.t.isoformat()+"Z")
    return ("timeout", 0, None, None)

# ── DB ─────────────────────────────────────────────────────────────────────
RESULTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS results(
  ts TEXT, coin_id TEXT, signal TEXT,
  price REAL, stop REAL, target REAL, rr REAL,
  ema200 REAL, rsi14 REAL, atr14 REAL,
  outcome TEXT, exit_price REAL, bars_to_outcome INTEGER, exit_time TEXT,
  r_realized REAL, pnl_pct REAL,
  evaluated_at TEXT
);
"""

def _ensure_tables(cur):
    cur.execute(RESULTS_SCHEMA)
    cur.execute("PRAGMA table_info(results)")
    cols = {r[1] for r in cur.fetchall()}
    need = {
        "exit_price":"REAL","bars_to_outcome":"INTEGER","exit_time":"TEXT",
        "r_realized":"REAL","pnl_pct":"REAL","evaluated_at":"TEXT"
    }
    for c,t in need.items():
        if c not in cols:
            cur.execute(f"ALTER TABLE results ADD COLUMN {c} {t}")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_results_key ON results(ts, coin_id, signal)")

def _already_done(cur, ts, coin_id, signal) -> bool:
    cur.execute("SELECT 1 FROM results WHERE ts=? AND coin_id=? AND signal=? LIMIT 1",
                (ts, coin_id, signal))
    return cur.fetchone() is not None

def _adaptive_horizon_bars(price: float, target: float, atr: float, max_hold: int) -> int:
    dist = abs(target - price)
    atr = max(atr, 1e-9)
    est = math.ceil(5.0 * dist / atr)   # longer horizon
    return max(1, min(est, max_hold))

# ── main ───────────────────────────────────────────────────────────────────
def evaluate_once():
    os.makedirs(config.DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    _ensure_tables(cur)

    sigs = pd.read_sql_query("SELECT * FROM signals ORDER BY ts", con)
    if sigs.empty:
        print("no signals to evaluate"); con.close(); return

    evaluated = 0
    for r in sigs.itertuples(index=False):
        ts_iso = r.ts
        side   = r.signal
        coin   = r.coin_id
        sym    = _symbol_for(coin)
        if not sym: continue
        if _already_done(cur, ts_iso, coin, side): continue

        # start 1 ms after signal time to capture same-bar events
        try:
            ts_dt = datetime.fromisoformat(ts_iso.replace("Z","+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            ts_dt = pd.to_datetime(ts_iso, utc=True).tz_convert("UTC").tz_localize(None).to_pydatetime()
        start_ms = int(ts_dt.timestamp()*1000) + 1

        horizon = _adaptive_horizon_bars(float(r.price), float(r.target), float(r.atr14), int(config.MAX_HOLD_BARS))
        fut = _klines(sym, config.BINANCE_INTERVAL, start_ms, horizon)
        if fut.empty: continue

        outcome, bars, exit_px, exit_time = _first_touch(side, fut, float(r.price), float(r.stop), float(r.target))

        price = float(r.price)
        if side == "LONG":
            risk = price - float(r.stop)
            r_realized = ((exit_px - price)/risk) if (risk>0 and exit_px is not None) else 0.0
            pnl_pct = ((exit_px/price - 1)*100.0) if exit_px is not None else 0.0
        else:
            risk = float(r.stop) - price
            r_realized = ((price - exit_px)/risk) if (risk>0 and exit_px is not None) else 0.0
            pnl_pct = ((1 - exit_px/price)*100.0) if exit_px is not None else 0.0

        evaluated_at = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

        cur.execute("""
        INSERT INTO results
        (ts,coin_id,signal,price,stop,target,rr,ema200,rsi14,atr14,
         outcome,exit_price,bars_to_outcome,exit_time,r_realized,pnl_pct,evaluated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ts_iso, coin, side, r.price, r.stop, r.target, r.rr, r.ema200, r.rsi14, r.atr14,
            outcome, float(exit_px) if exit_px is not None else None, int(bars), exit_time,
            round(float(r_realized),3), round(float(pnl_pct),3), evaluated_at
        ))
        evaluated += 1

    con.commit(); con.close()
    print(f"evaluated {evaluated} signals")

if __name__ == "__main__":
    evaluate_once()
