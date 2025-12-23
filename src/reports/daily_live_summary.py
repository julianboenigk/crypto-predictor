from __future__ import annotations

from src.bootstrap.env import PROJECT_ROOT  # loads .env via side-effect

import json
import os
from datetime import datetime, UTC, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ============================================================
# Telegram
# ============================================================

try:
    from src.core.notify import send_telegram  # type: ignore
except Exception as e:
    print(f"[WARN] Telegram import failed: {e}")
    send_telegram = None  # type: ignore

# ============================================================
# Paths (ABSOLUTE → cron-safe)
# ============================================================

DATA_DIR = PROJECT_ROOT / "data"
PAPER_TRADES_PATH = DATA_DIR / "paper_trades_closed.jsonl"
TESTNET_TRADES_PATH = DATA_DIR / "testnet_trades.jsonl"

# ============================================================
# Helpers
# ============================================================

def _fmt_pct(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_float(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}"


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def _load_trades(path: Path) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    if not path.exists():
        return trades

    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trades.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print(f"[WARN] Failed reading {path}: {e}")
        return []

    return trades


def _filter_last_24h(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    out: List[Dict[str, Any]] = []
    for tr in trades:
        ts = (
            _parse_ts(tr.get("exit_time"))
            or _parse_ts(tr.get("t"))
            or _parse_ts(tr.get("time"))
            or _parse_ts(tr.get("closed_at"))
        )
        if ts and ts >= cutoff:
            out.append(tr)

    return out


def _classify_outcome(tr: Dict[str, Any]) -> Tuple[bool | None, float]:
    pnl_r = 0.0
    raw_pnl = tr.get("pnl_r", tr.get("r"))

    if raw_pnl is not None:
        try:
            pnl_r = float(raw_pnl)
        except Exception:
            pnl_r = 0.0

    outcome = str(tr.get("outcome", "")).upper()
    status = str(tr.get("status", "")).lower()

    if outcome == "TP":
        return True, pnl_r
    if outcome == "SL":
        return False, pnl_r

    if "win" in status:
        return True, pnl_r
    if "loss" in status or "lose" in status:
        return False, pnl_r

    if pnl_r > 0:
        return True, pnl_r
    if pnl_r < 0:
        return False, pnl_r

    return None, pnl_r


def compute_stats(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "n_trades": 0,
            "wins": 0,
            "losses": 0,
            "unknown": 0,
            "winrate": None,
            "pnl_r": None,
            "expectancy_r": None,
            "profit_factor": None,
        }

    wins = losses = unknown = 0
    pnl_values: List[float] = []

    for tr in trades:
        is_win, pnl_r = _classify_outcome(tr)
        pnl_values.append(pnl_r)

        if is_win is True:
            wins += 1
        elif is_win is False:
            losses += 1
        else:
            unknown += 1

    n = len(trades)
    pnl_total = sum(pnl_values)

    gross_win = sum(v for v in pnl_values if v > 0)
    gross_loss = -sum(v for v in pnl_values if v < 0)

    return {
        "n_trades": n,
        "wins": wins,
        "losses": losses,
        "unknown": unknown,
        "winrate": wins / n if n else None,
        "pnl_r": pnl_total,
        "expectancy_r": pnl_total / n if n else None,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else None,
    }

# ============================================================
# Message
# ============================================================

def build_message(
    stats_paper: Dict[str, Any],
    stats_testnet: Dict[str, Any] | None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "📊 Live Trading – letzte 24h",
        f"Stand: {now}",
        "",
        "Paper-Trades:",
        f"- Trades: {stats_paper['n_trades']}",
        f"- Wins: {stats_paper['wins']}, Losses: {stats_paper['losses']}, Unknown: {stats_paper['unknown']}",
        f"- Winrate: {_fmt_pct(stats_paper['winrate'])}",
        f"- Ergebnis: {_fmt_float(stats_paper['pnl_r'], 1)} R",
        f"- Expectancy: {_fmt_float(stats_paper['expectancy_r'], 3)} R/Trade",
        f"- Profit Factor: {_fmt_float(stats_paper['profit_factor'], 2)}",
    ]

    if stats_testnet:
        lines += [
            "",
            "Testnet-Trades:",
            f"- Trades: {stats_testnet['n_trades']}",
            f"- Ergebnis: {_fmt_float(stats_testnet['pnl_r'], 1)} R",
        ]

    lines.append("")
    lines.append("Hinweis: Nur abgeschlossene Trades der letzten 24h.")

    return "\n".join(lines)

# ============================================================
# Main
# ============================================================

def main() -> None:
    paper = _filter_last_24h(_load_trades(PAPER_TRADES_PATH))
    testnet = _filter_last_24h(_load_trades(TESTNET_TRADES_PATH))

    stats_paper = compute_stats(paper)
    stats_testnet = compute_stats(testnet) if testnet else None

    print(json.dumps(
        {
            "run_at": datetime.now(UTC).isoformat(),
            "paper": stats_paper,
            "testnet": stats_testnet,
        },
        indent=2,
    ))

    has_trades = stats_paper["n_trades"] > 0 or (
        stats_testnet and stats_testnet["n_trades"] > 0
    )

    if not has_trades:
        print("[INFO] No trades in last 24h → no Telegram message")
        return

    if send_telegram is None:
        print("[WARN] Telegram skipped: send_telegram is None")
        return

    if os.getenv("TELEGRAM_LIVE_SUMMARY", "true").lower() != "true":
        print("[INFO] Telegram disabled via TELEGRAM_LIVE_SUMMARY")
        return

    msg = build_message(stats_paper, stats_testnet)
    if len(msg) > 3500:
        msg = msg[:3400] + "\n\n[gekürzt]"

    send_telegram(msg)
    print("[INFO] Telegram live summary sent")


if __name__ == "__main__":
    main()
