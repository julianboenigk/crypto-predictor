# src/utils/notify_from_log.py
from __future__ import annotations
import argparse
import re
from pathlib import Path
from typing import List

from .notify_telegram import send_alert

CONSENSUS_RE = re.compile(
    r"^\[CONSENSUS\]\s+([A-Z]+USDT)\s+([A-Z]+)\s+S=([+-]?\d+\.\d+).*$"
)

def parse_bullets(text: str, max_items: int = 12) -> List[str]:
    bullets: List[str] = []
    for line in text.splitlines():
        m = CONSENSUS_RE.match(line.strip())
        if not m:
            continue
        pair, action, score = m.groups()
        bullets.append(f"{pair}: *{action}* (S={score})")
        if len(bullets) >= max_items:
            break
    return bullets

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="data/logs/main.log", help="Path to main.log")
    ap.add_argument("--dry-run", action="store_true", help="Print instead of sending")
    args = ap.parse_args()

    p = Path(args.log)
    if not p.exists():
        print(f"Log not found: {p}")
        return 2

    text = p.read_text(errors="ignore")
    bullets = parse_bullets(text)
    if not bullets:
        print("No consensus entries found to send.")
        return 0

    title = "Crypto Predictor — Latest Consensus"
    if args.dry_run:
        print(title)
        for b in bullets:
            print(f" - {b}")
        return 0

    ok = send_alert(title, bullets)
    print("Sent." if ok else "Failed.")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
