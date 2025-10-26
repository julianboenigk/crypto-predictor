from __future__ import annotations
import argparse, csv, time
from pathlib import Path
import yaml
from src.core.store import init_db
from src.data.binance_client import get_ohlcv

def load_cfg(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def write_csv(pair: str, rows: list[list[float]]) -> Path:
    out = Path("data") / f"{pair}_15m.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["open_time_ms","open","high","low","close","volume","close_time_ms"])
    with open(out, "a", newline="") as f:
        w = csv.writer(f)
        for r in rows:
            w.writerow(r)
    return out

def run_once() -> int:
    cfg = load_cfg("configs/universe.yaml")
    pairs = cfg["pairs"]
    interval = cfg["interval"]
    max_age = int(cfg["max_input_age_sec"]) * 1000
    init_db()

    ok = 0
    for p in pairs:
        rows, server_time = get_ohlcv(p, interval, limit=1_000)
        # freshness check: last candle close_time within max_age of server_time
        fresh = (server_time - rows[-1][6]) <= max_age
        out = write_csv(p, rows[-100:])  # append last 100 for speed
        status = "FRESH" if fresh else "STALE"
        print(f"[{status}] {p} rows_appended=100 file={out}")
        ok += int(fresh)
    return 0 if ok == len(pairs) else 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"], nargs="?", default="run")
    args = ap.parse_args()
    raise SystemExit(run_once())
