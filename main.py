import os, csv, time
from pathlib import Path
import pandas as pd
import config
from fetcher import get_markets, load_all_ohlc
from analyzer import scan_all
from notifier import send_telegram, fmt_signal

def ensure_dirs():
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(os.path.dirname(config.LOG_FILE)).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(config.LOG_FILE):
        with open(config.LOG_FILE, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts","coin_id","signal","price","stop","target","rr","expected_return_pct","ema200","rsi14","atr14"])

def log_signal(s: dict):
    with open(config.LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            s["timestamp"], s["coin_id"], s["signal"], s["price"], s["stop"],
            s["target"], s["rr"], s["expected_return_pct"], s["ema200"], s["rsi14"], s["atr14"]
        ])

def dedupe_signals(signals):
    if not os.path.exists(config.LOG_FILE): return signals
    df = pd.read_csv(config.LOG_FILE)
    out = []
    for s in signals:
        recent = df[(df.coin_id==s["coin_id"]) & (df.signal==s["signal"])].tail(1)
        out.append(s) if recent.empty else out.append(s)
    return out

def run_once():
    ensure_dirs_
