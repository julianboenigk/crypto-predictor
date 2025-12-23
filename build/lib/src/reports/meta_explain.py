# src/reports/meta_explain.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Tuple

from src.core.llm import simple_completion

try:
    from src.core.notify import send_telegram  # optional
except Exception:  # pragma: no cover
    send_telegram = None  # type: ignore

RUNS_PATH = Path("data/runs.log")
OUT_DIR = Path("data/reports")
OUT_FILE = OUT_DIR / "meta_explanations_latest.jsonl"

MIN_ABS_SCORE = float(os.getenv("META_MIN_ABS_SCORE", "0.7"))


def _tail_last_run() -> Dict[str, Any] | None:
    if not RUNS_PATH.exists():
        return None
    with RUNS_PATH.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except Exception:
        return None


def _select_strong_signals(run_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = run_obj.get("results", [])
    out: List[Dict[str, Any]] = []
    for r in results:
        score = float(r.get("score", 0.0))
        decision = str(r.get("decision", "HOLD")).upper()
        if decision in ("LONG", "SHORT") and abs(score) >= MIN_ABS_SCORE:
            out.append(r)
    return out


def _build_debate_prompt(run_obj: Dict[str, Any]) -> str:
    strong = _select_strong_signals(run_obj)
    if not strong:
        return ""

    parts: List[str] = []
    for r in strong:
        pair = r.get("pair")
        score = float(r.get("score", 0.0))
        decision = str(r.get("decision", "HOLD")).upper()
        breakdown: List[Tuple[str, float, float]] = r.get("breakdown", [])
        weights: Dict[str, float] = r.get("weights", {})

        parts.append(f"PAIR: {pair}")
        parts.append(f"Final score S: {score:+.3f}, decision: {decision}")
        parts.append("Agents:")
        for name, s, c in breakdown:
            w = weights.get(name, None)
            if w is None:
                parts.append(f"  - {name}: score={s:+.3f}, conf={c:.2f}")
            else:
                parts.append(f"  - {name}: score={s:+.3f}, conf={c:.2f}, weight={w:.2f}")
        parts.append("----")

    return "\n".join(parts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    run_obj = _tail_last_run()
    if not run_obj:
        print("no runs found")
        return

    user_prompt = _build_debate_prompt(run_obj)
    if not user_prompt:
        print("no strong signals to explain")
        return

    system_prompt = """
Du agierst als Meta-Agent für ein Multi-Agenten-Trading-System.
Es gibt mehrere Agenten (z.B. Technical, News, Sentiment, Research), die für ein Asset jeweils
Score, Confidence und Gewicht beitragen. Du erhältst für starke Signale die finale Entscheidung
(LONG/SHORT) plus Agent-Breakdown.

Deine Aufgaben:
1. Erkläre pro Asset in 2–3 Bulletpoints, warum die Entscheidung plausibel oder riskant ist.
2. Hebe Konflikte zwischen Agenten hervor (z.B. Technical bullish, News bearish).
3. Formuliere pro Asset genau einen kurzen Satz zu den größten Risiken/Unsicherheiten.
4. Sei präzise, keine Floskeln, keine Wiederholung offensichtlicher Details.

Antwortformat:
PAIR: <pair>
- Punkt 1
- Punkt 2
- Risiko: ...
(Leerzeile zwischen Assets)
""".strip()

    text = simple_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_env_var="OPENAI_MODEL_META",
        default_model="gpt-5.1-2025-11-13",
        max_tokens=900,
        context="meta_explain",
    )

    obj = {
        "run_at": run_obj.get("run_at"),
        "explanation": text,
    }

    with OUT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(text)

    # Optional: per Telegram schicken
    if send_telegram is not None and text.strip():
        if os.getenv("TELEGRAM_META_ENABLED", "false").lower() == "true":
            header = "Meta-Review der letzten starken Signale:\n\n"
            msg = (header + text).strip()
            if len(msg) > 3500:
                msg = msg[:3400] + "\n\n[gekürzt]"
            send_telegram(msg)


if __name__ == "__main__":
    main()
