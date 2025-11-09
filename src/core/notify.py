# src/core/notify.py
from __future__ import annotations
import os
import requests
from typing import List, Tuple, Optional
from datetime import datetime, timezone


def send_telegram(message: str, parse_mode: Optional[str] = "Markdown") -> bool:
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        return False

    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        r = requests.post(url, json=payload, timeout=10)
        return r.ok and bool(r.json().get("ok"))
    except Exception:
        return False


def format_signal_message(
    pair: str,
    decision: str,
    score: float,
    breakdown: List[Tuple[str, float, float]],
    reason: str,
) -> str:
    emoji_map = {"LONG": "🟢", "SHORT": "🔴", "HOLD": "⏸️"}
    action_text = {
        "LONG": "Buy signal",
        "SHORT": "Sell signal",
        "HOLD": "Hold / no clear edge",
    }

    pair_pretty = pair.replace("USDT", "/USDT")
    emoji = emoji_map.get(decision.upper(), "ℹ️")
    action_line = action_text.get(decision.upper(), "Signal")

    tech_line = ""
    news_line = ""
    sent_line = ""
    research_line = ""

    for name, s, c in breakdown:
        name_l = name.lower()
        conf_pct = int(round(c * 100))
        if name_l == "technical":
            if s > 0.3:
                desc = "bullish setup"
            elif s < -0.3:
                desc = "bearish setup"
            else:
                desc = "neutral pattern"
            tech_line = f"🧭 *Technicals* → {desc} ({conf_pct}% conf.)"
        elif name_l == "news":
            if s > 0.2:
                desc = "positive headlines"
            elif s < -0.2:
                desc = "negative headlines"
            else:
                desc = "neutral news"
            news_line = f"📰 *News* → {desc} ({conf_pct}% conf.)"
        elif name_l == "sentiment":
            if s > 0.2:
                desc = "market upbeat"
            elif s < -0.2:
                desc = "market cautious"
            else:
                desc = "market neutral"
            sent_line = f"📊 *Sentiment* → {desc} ({conf_pct}% conf.)"
        elif name_l == "research":
            if s > 0.2:
                desc = "research supportive"
            elif s < -0.2:
                desc = "research critical"
            else:
                desc = "research neutral"
            research_line = f"📚 *Research* → {desc} ({conf_pct}% conf.)"

    if decision.upper() == "LONG":
        interpretation = "Multiple signals point up."
    elif decision.upper() == "SHORT":
        interpretation = "Downward pressure dominates."
    else:
        interpretation = "Signals mixed. Waiting is reasonable."

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"🔹 *{pair_pretty} — Market Check*",
        f"Current Signal: {emoji} *{action_line}*",
        f"Score: `{score:+.2f}` (range −1 → +1)",
        "",
    ]
    if tech_line:
        lines.append(tech_line)
    if news_line:
        lines.append(news_line)
    if sent_line:
        lines.append(sent_line)
    if research_line:
        lines.append(research_line)

    lines.append("")
    lines.append(f"💡 {interpretation}")
    lines.append(f"_Reason: {reason}_")
    lines.append(f"\n_Last update: {ts}_")

    return "\n".join(lines)
