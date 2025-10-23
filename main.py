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

def run_once():
    init_db()
    ensure_dirs()

    # universe
    try:
        keys = get_top_symbols(config.DYNAMIC_TOP_N) if config.USE_DYNAMIC_SYMBOLS else config.COIN_IDS
    except Exception:
        keys = config.COIN_IDS

    # data + analysis
    ohlc_map = load_all_ohlc(keys)
    signals = dedupe_signals(scan_all(ohlc_map))

    # sentiment context
    fng = fetch_fng()
    ctx = {"fng": fng}

    # outputs
    for s in signals:
        log_signal_csv(s)
        insert_signal(s)
        send_telegram(fmt_signal(s, ctx))

    print(f"universe={len(keys)} data={len(ohlc_map)} signals={len(signals)} FNG={fng.get('value')}")

if __name__ == "__main__":
    run_once()
