# src/utils/notify_from_log.py
# -----------------------------------------------------------------------------
# Reads all trade plans from data/plans/*.json and sends a Telegram notification
# for those with certainty >= threshold (default 70%).
# -----------------------------------------------------------------------------

from __future__ import annotations
import os
import json
import glob
from typing import Dict, Any, List
from src.utils.notify_telegram import send_message


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
THRESH = float(os.getenv("CERTAINTY_NOTIFY_THRESHOLD", "70"))


# --------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------

def load_plans() -> Dict[str, Any]:
    """Load all trade plan JSON files from data/plans."""
    plans: Dict[str, Any] = {}
    for fp in glob.glob("data/plans/*.json"):
        try:
            with open(fp, "r") as f:
                obj = json.load(f)
                if isinstance(obj, dict) and "pair" in obj:
                    plans[obj["pair"]] = obj
        except Exception as e:
            print(f"[WARN] Failed to load {fp}: {e}")
    return plans


def fmt_pair(p: str) -> str:
    """Format pair name for readability (e.g. BTCUSDT → BTC)."""
    return p.replace("USDT", "")


def format_high_conviction(plans: Dict[str, Any]) -> str | None:
    """Format Markdown message for all high-certainty BUY/SELL trades."""
    lines: List[str] = []

    for pair, plan in sorted(plans.items()):
        act = plan.get("action", "HOLD")
        cert = float(plan.get("certainty_pct", 0.0))
        if act == "HOLD" or cert < THRESH:
            continue

        entry = plan.get("entry")
        sl = plan.get("stop")
        tp1 = plan.get("tp1")
        tp2 = plan.get("tp2")
        valid = plan.get("valid_until")

        emoji = "🚀" if act == "BUY" else "🔻"
        lines.append(
            f"*{fmt_pair(pair)}*: {emoji} *{act}*  _Certainty {cert:.0f}%_\n"
            f"• Entry: {entry} ({plan.get('entry_type','limit')})\n"
            f"• Stop-Loss: {sl}\n"
            f"• Take-Profit 1: {tp1}\n"
            f"• Take-Profit 2: {tp2}\n"
            f"• Valid until: {valid}"
        )

    if not lines:
        return None

    header = f"📣 *High-Conviction Trade Plans* (≥ {int(THRESH)} %)"
    return header + "\n\n" + "\n\n".join(lines)


# --------------------------------------------------------------------------
# Main entry
# --------------------------------------------------------------------------

def main() -> int:
    plans = load_plans()
    text = format_high_conviction(plans)

    if not text:
        print("[INFO] No high-conviction trades to notify.")
        return 0

    ok = send_message(text, parse_mode="Markdown")
    print("[OK] Telegram notification sent." if ok else "[ERR] Telegram send failed.")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
