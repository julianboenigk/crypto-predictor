from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import yaml

from src.core.store import (
    init_db,
    start_run,
    end_run,
    save_agent_output,
    save_signal,
)
from src.data.binance_client import get_ohlcv
from src.agents.technical import TechnicalAgent
from src.agents.base import Candle
from src.core.consensus import decide


def load_cfg(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)  # type: ignore[no-any-return]


def write_csv(pair: str, rows: list[list[float | int]]) -> Path:
    out = Path("data") / f"{pair}_15m.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["open_time_ms", "open", "high", "low", "close", "volume", "close_time_ms"])
    if rows:
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
    ta = TechnicalAgent()

    started = datetime.now(timezone.utc).isoformat()
    run_id = start_run(started, notes=f"interval={interval}")

    try:
        ok_pairs = 0

        for p in pairs:
            rows, server_time = get_ohlcv(p, interval, limit=1000)

            if not rows:
                print(f"[ERROR] {p} no rows returned")
                continue

            fresh = (server_time - rows[-1][6]) <= max_age
            out = write_csv(p, rows[-100:])
            status = "FRESH" if fresh else "STALE"
            print(f"[{status}] {p} rows_appended=100 file={out}")

            # --- Technical agent ---
            last = rows[-250:]
            candles: list[Candle] = [
                {
                    "t": int(r[6]),
                    "o": float(r[1]),
                    "h": float(r[2]),
                    "low": float(r[3]),
                    "c": float(r[4]),
                    "v": float(r[5]),
                }
                for r in last
            ]
            res = ta.run(p, candles, inputs_fresh=fresh)
            print(
                f"[TECH] {p} score={res['score']:+.2f} "
                f"conf={res['confidence']:.2f} :: {res['explanation']}"
            )

            save_agent_output(
                run_id,
                p,
                "technical",
                res["score"],
                res["confidence"],
                res["explanation"],
                res["inputs_fresh"],
                res["latency_ms"],
            )

            # --- Consensus (currently only technical agent) ---
            decision = decide(
                [
                    {
                        "agent": "technical",
                        "score": res["score"],
                        "confidence": res["confidence"],
                        "explanation": res["explanation"],
                    }
                ]
            )

            save_signal(
                run_id,
                p,
                decision["consensus"],
                decision["decision"],
                decision["reason"],
            )

            print(
                f"[CONSENSUS] {p} {decision['decision']} "
                f"S={decision['consensus']:+.3f} :: {decision['reason']}"
            )

            ok_pairs += int(fresh)

        finished = datetime.now(timezone.utc).isoformat()
        status = "ok" if ok_pairs == len(pairs) else "partial"
        end_run(run_id, finished, status=status, notes=f"fresh={ok_pairs}/{len(pairs)}")
        return 0 if status == "ok" else 1

    except Exception as exc:
        finished = datetime.now(timezone.utc).isoformat()
        end_run(run_id, finished, status="error", notes=str(exc))
        raise


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"], nargs="?", default="run")
    ap.parse_args()
    raise SystemExit(run_once())
