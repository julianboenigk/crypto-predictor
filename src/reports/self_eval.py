# src/reports/self_eval.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from src.core.llm import simple_completion

try:
    from src.core.notify import send_telegram  # optional
except Exception:  # pragma: no cover
    send_telegram = None  # type: ignore

BACKTEST_DIR = Path("data/backtests")
OUT_DIR = Path("data/reports")


def _latest_backtest_file() -> Path | None:
    if not BACKTEST_DIR.exists():
        return None
    files = sorted(BACKTEST_DIR.glob("backtest_*.json"), reverse=True)
    return files[0] if files else None


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _summarize_trades(bt: Dict[str, Any]) -> str:
    trades: List[Dict[str, Any]] = bt.get("trades", [])
    if not trades:
        return "No trades in backtest."

    total = len(trades)
    losses = [t for t in trades if t.get("outcome") == "SL"]
    wins = [t for t in trades if t.get("outcome") == "TP"]

    by_pair: Dict[str, Dict[str, int]] = {}
    for t in trades:
        pair = t.get("pair", "UNKNOWN")
        side = t.get("side", "UNKNOWN")
        out = t.get("outcome", "UNKNOWN")
        if pair not in by_pair:
            by_pair[pair] = {"TP_LONG": 0, "SL_LONG": 0, "TP_SHORT": 0, "SL_SHORT": 0}
        key = f"{out}_{side}"
        if key in by_pair[pair]:
            by_pair[pair][key] += 1

    lines: List[str] = []
    lines.append(f"Total trades: {total}")
    lines.append(f"Wins (TP): {len(wins)}")
    lines.append(f"Losses (SL): {len(losses)}")
    lines.append("")
    lines.append("Per pair and side (counts TP/SL):")
    for pair, stats in by_pair.items():
        lines.append(f"- {pair}: {stats}")

    lines.append("")
    lines.append("Sample losing trades (up to 5):")
    for t in losses[:5]:
        lines.append(
            f"* {t.get('pair')} {t.get('side')} "
            f"entry={t.get('entry')} sl={t.get('stop_loss')} tp={t.get('take_profit')} "
            f"close_reason={t.get('close_reason')}"
        )

    return "\n".join(lines)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = _latest_backtest_file()
    if latest_path is None:
        print("no backtest files found")
        return

    bt = _load_json(latest_path)
    stats_text = _summarize_trades(bt)

    system_prompt = """
Du bist ein kritischer, aber konstruktiver Trading-Reviewer.
Du bekommst eine Zusammenfassung eines Backtests (Trades, Wins/Losses, Verteilung
nach Paar und Richtung).

Deine Aufgaben:
1. Identifiziere systematische Schwächen (z.B. zu viele Short-Verluste in Seitwärtsmärkten,
   bestimmte Paare mit schlechter Performance, Übergewichtung eines Signals).
2. Formuliere 3–5 konkrete Beobachtungen, mit Fokus auf Muster, nicht Einzelfälle.
3. Gib 3–5 konkrete Vorschläge, wie das System angepasst werden kann
   (z.B. Filter, geänderte Schwellen, Anpassungen an Agenten, Zeitfenster).
4. Halte dich kurz, präzise und strukturiert (Bulletpoints).

Antworte in Deutsch.
""".strip()

    user_prompt = f"Backtest-Zusammenfassung:\n\n{stats_text}"

    analysis = simple_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_env_var="OPENAI_MODEL_SELF_EVAL",
        default_model="gpt-5.1-2025-11-13",
        max_tokens=900,
	context="self_eval",
    )

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"self_eval_{ts}.txt"
    out_path.write_text(analysis, encoding="utf-8")

    print(f"Self-evaluation written to: {out_path}")
    print()
    print(analysis)

    # Optional: per Telegram schicken
    if send_telegram is not None and analysis.strip():
        if os.getenv("TELEGRAM_SELF_EVAL", "true").lower() == "true":
            # Telegram hat ein Limit, wir schneiden sicherheitshalber etwas ab
            header = "Weekly self-evaluation (Backtest):\n\n"
            msg = (header + analysis).strip()
            if len(msg) > 3500:
                msg = msg[:3400] + "\n\n[gekürzt]"
            send_telegram(msg)


if __name__ == "__main__":
    main()
