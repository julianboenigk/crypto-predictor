# src/core/notify.py
from __future__ import annotations

import os
from typing import List, Tuple, Optional, Dict, Any

import requests

from src.core.timeutil import fmt_local


def send_telegram(message: str, parse_mode: Optional[str] = "Markdown") -> bool:
    """
    Sendet eine Textnachricht an Telegram, wenn TELEGRAM_ENABLED=true und Token + Chat-ID vorhanden sind.
    """
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        return False

    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            return False
        data = r.json()
        return bool(data.get("ok"))
    except Exception:
        return False


def send_telegram_photo(photo_path: str, caption: str = "") -> bool:
    """
    Sendet ein Bild (z. B. PNG) an Telegram. Optional mit Caption.
    """
    if os.getenv("TELEGRAM_ENABLED", "false").lower() != "true":
        return False

    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False
    if not os.path.exists(photo_path):
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        with open(photo_path, "rb") as f:
            files = {"photo": f}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "Markdown",
            }
            r = requests.post(url, data=data, files=files, timeout=15)
        if not r.ok:
            return False
        data = r.json()
        return bool(data.get("ok"))
    except Exception:
        return False


def format_signal_message(
    pair: str,
    decision: str,
    score: float,
    breakdown: List[Tuple[str, float, float]],
    reason: str,
    order_levels: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Baut eine kompakte, menschlich lesbare Telegram-Nachricht aus einem berechneten Signal.
    """
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
        name_l = str(name).lower()
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

    ts = fmt_local()

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

    if order_levels:
        entry = order_levels.get("entry")
        sl = order_levels.get("stop_loss")
        tp = order_levels.get("take_profit")
        rr = order_levels.get("rr")
        lines.append("")
        lines.append("🧾 *Paper trade levels*")
        if entry is not None:
            lines.append(f"- Entry: `{entry}`")
        if sl is not None:
            lines.append(f"- Stop-Loss: `{sl}`")
        if tp is not None:
            lines.append(f"- Take-Profit: `{tp}`")
        if rr is not None:
            lines.append(f"- R:R: `{rr}`")

    lines.append("")
    lines.append(f"💡 {interpretation}")
    lines.append(f"_Reason: {reason}_")
    lines.append(f"\n_Last update: {ts}_")

    return "\n".join(lines)
