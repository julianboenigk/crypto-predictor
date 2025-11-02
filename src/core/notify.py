# src/core/notify.py
from __future__ import annotations
import os, time, requests
from typing import List, Tuple, Optional
from datetime import datetime, timezone


# ---------- TELEGRAM SENDER ----------
def send_telegram(message: str, parse_mode: Optional[str] = "Markdown") -> bool:
    """Send a nicely formatted Telegram message."""
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


# ---------- MESSAGE FORMATTER ----------
def format_signal_message(
    pair: str,
    decision: str,
    score: float,
    breakdown: List[Tuple[str, float, float]],
    reason: str,
) -> str:
    """
    Create a natural-language Telegram message for non-technical users.
    """

    # Friendly pair + icons
    emoji_map = {"LONG": "🟢", "SHORT": "🔴", "HOLD": "⏸️"}
    action_text = {
        "LONG": "Buy signal (bullish momentum)",
        "SHORT": "Sell signal (bearish pressure)",
        "HOLD": "Hold — no clear trend",
    }

    emoji = emoji_map.get(decision.upper(), "ℹ️")
    action_line = action_text.get(decision.upper(), "Market update")

    # Pretty pair name
    pair_pretty = pair.replace("USDT", "/USDT")

    # Interpret breakdowns
    tech_line = news_line = ""
    for name, s, c in breakdown:
        conf_pct = int(round(c * 100))
        if name.lower() == "technical":
            if s > 0.3:
                desc = "bullish setup"
            elif s < -0.3:
                desc = "bearish tendency"
            else:
                desc = "neutral pattern"
            tech_line = f"🧭 *Technicals* → {desc} ({conf_pct}% confidence)"
        elif name.lower() == "news":
            if s > 0.2:
                desc = "positive headlines"
            elif s < -0.2:
                desc = "negative headlines"
            else:
                desc = "neutral news mood"
            news_line = f"📰 *News Sentiment* → {desc} ({conf_pct}% confidence)"

    # Friendly interpretation text
    interpretation = ""
    if decision.upper() == "LONG":
        interpretation = "Momentum and sentiment are aligned upward — a good moment to consider entering a position."
    elif decision.upper() == "SHORT":
        interpretation = "Downward pressure dominates — caution, market may continue lower."
    else:
        interpretation = "Signals are mixed; staying on the sidelines may be prudent until a clearer trend forms."

    # Timestamp
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Compose message
    lines = [
        f"🔹 *{pair_pretty} — Market Check*",
        f"Current Signal: {emoji} *{action_line}*",
        f"Score: `{score:+.2f}` (range −1 → +1)",
        "",
    ]
    if tech_line: lines.append(tech_line)
    if news_line: lines.append(news_line)
    lines.append("")
    lines.append(f"💡 *Interpretation:* {interpretation}")
    lines.append(f"_Reason: {reason}_")
    lines.append(f"\n_Last update: {ts}_")

    return "\n".join(lines)
