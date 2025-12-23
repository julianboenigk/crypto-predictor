# src/reports/self_eval.py
from __future__ import annotations

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


import json
import os
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from src.core.llm import simple_completion

try:
    from src.core.notify import send_telegram  # optional
except Exception:  # pragma: no cover
    send_telegram = None  # type: ignore


BACKTEST_DIR = Path("data/backtests")
OUT_DIR = Path("data/reports")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
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


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = _latest_backtest_file()
    if latest_path is None:
        print("no backtest files found")
        return

    bt = _load_json(latest_path)
    stats_text = _summarize_trades(bt)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"self_eval_{ts}.txt"

    # --------------------------------------------------------------
    # Guard: OpenAI key missing → graceful fallback
    # --------------------------------------------------------------
    if not os.getenv("OPENAI_API_KEY"):
        fallback = (
            "SELF-EVALUATION SKIPPED (no OPENAI_API_KEY)\n\n"
            "Backtest summary:\n\n"
            f"{stats_text}\n\n"
            "To enable AI-based self evaluation, set OPENAI_API_KEY."
        )
        out_path.write_text(fallback, encoding="utf-8")
        print(f"Self-evaluation skipped (no API key). Written to: {out_path}")

        if send_telegram is not None:
            send_telegram(
                "⚠️ Self-evaluation skipped: OPENAI_API_KEY not set.\n"
                "A fallback summary was written to disk."
            )
        return

    # --------------------------------------------------------------
    # AI-based evaluation
    # --------------------------------------------------------------
    system_prompt = """
Du bist ein kritischer, aber konstruktiver Trading-Reviewer.
Du bekommst eine Zusammenfassung eines Backtests (Trades, Wins/Losses, Verteilung
nach Paar und Richtung).

Deine Aufgaben:
1. Identifiziere systematische Schwächen.
2. Formuliere 3–5 konkrete Beobachtungen (Muster, keine Einzelfälle).
3. Gib 3–5 konkrete Verbesserungsvorschläge.
4. Kurz, präzise, strukturiert (Bulletpoints).

Antworte in Deutsch.
""".strip()

    user_prompt = f"Backtest-Zusammenfassung:\n\n{stats_text}"

    analysis = simple_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_env_var="OPENAI_MODEL_SELF_EVAL",
        default_model="gpt-4.1-mini",
        max_tokens=900,
        context="self_eval",
    )

    out_path.write_text(analysis, encoding="utf-8")

    print(f"Self-evaluation written to: {out_path}")
    print()
    print(analysis)

    if send_telegram is not None and analysis.strip():
        if os.getenv("TELEGRAM_SELF_EVAL", "true").lower() == "true":
            header = "Weekly self-evaluation (Backtest):\n\n"
            msg = (header + analysis).strip()
            if len(msg) > 3500:
                msg = msg[:3400] + "\n\n[gekürzt]"
            send_telegram(msg)


if __name__ == "__main__":
    main()
