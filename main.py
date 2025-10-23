import os, csv
from pathlib import Path
import pandas as pd
import config
from fetcher import get_markets, load_all_ohlc, get_top_symbols
from analyzer import scan_all
from notifier import send_telegram, fmt_signal
from db_logger import init_db, insert_signal
from sentiment import fetch_fng

def ensure_dirs():
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    log_dir = os.path.dirname(config.LOG_FILE) or "."
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, "w", newline="") as f:
            csv.writer(f).writerow([
                "ts","coin_id","signal","price","stop","target","rr",
                "expected_return_pct","ema200","rsi14","atr14"
            ])

def log_signal_csv(s: dict):
    with open(config.LOG_FILE, "a", newline="") as f:
        csv.writer(f).writerow([
            s["timestamp"], s["coin_id"], s["signal"], s["price"], s["stop"],
            s["target"], s["rr"], s["expected_return_pct"],
            s["ema200"], s["rsi14"], s["atr14"]
        ])

def dedupe_signals(signals):
    if not os.path.exists(config.LOG_FILE): return signals
    try:
        df = pd.read_csv(config.LOG_FILE)
    except Exception:
        return signals
    out = []
    for s in signals:
        recent = df[(df.coin_id==s["coin_id"]) & (df.signal==s["signal"])].tail(1)
        out.append(s) if recent.empty else out.append(s)
    return out

def _bar_minutes() -> int:
    m = {"1m":1,"3m":3,"5m":5,"15m":15,"30m":30,"1h":60,"2h":120,"4h":240,"1d":1440}
    return m.get(config.BINANCE_INTERVAL, 60)

def run_once():
    init_db()
    ensure_dirs()

    try:
        keys = get_top_symbols(config.DYNAMIC_TOP_N) if config.USE_DYNAMIC_SYMBOLS else config.COIN_IDS
    except Exception:
        keys = config.COIN_IDS

    ohlc_map = load_all_ohlc(keys)
    signals = dedupe_signals(scan_all(ohlc_map))

    bar_min = _bar_minutes()
    fng = fetch_fng()

    for s in signals:
        ts = pd.to_datetime(s["timestamp"])
        entry_until = ts + pd.Timedelta(minutes=bar_min * config.ENTRY_VALID_BARS)
        dist = abs(float(s["target"]) - float(s["price"]))
        atr = max(float(s["atr14"]), 1e-9)
        est_bars = max(1, int(round(dist / atr)))
        est_exit = ts + pd.Timedelta(minutes=bar_min * est_bars)
        force_exit = ts + pd.Timedelta(minutes=bar_min * config.MAX_HOLD_BARS)

        ctx = {
            "fng": fng,
            "timing": {
                "entry_until": entry_until.strftime("%Y-%m-%d %H:%M:%S%z"),
                "est_exit":    est_exit.strftime("%Y-%m-%d %H:%M:%S%z"),
                "force_exit":  force_exit.strftime("%Y-%m-%d %H:%M:%S%z"),
            },
        }

        log_signal_csv(s)
        insert_signal(s)
        send_telegram(fmt_signal(s, ctx))

    print(f"universe={len(keys)} data={len(ohlc_map)} signals={len(signals)} FNG={fng.get('value')}")

if __name__ == "__main__":
    run_once()
