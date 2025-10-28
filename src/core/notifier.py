from __future__ import annotations
import os
import json
import time
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()

def _env(name: str, default: str = "") -> str:
    v = os.getenv(name, default)
    return v if v is not None else default

_ENABLED = _env("TELEGRAM_ENABLED", "false").lower() == "true"
_TOKEN = _env("TELEGRAM_TOKEN")
_CHAT_ID = _env("TELEGRAM_CHAT_ID")

def telegram_enabled() -> bool:
    return _ENABLED and bool(_TOKEN) and bool(_CHAT_ID)

def send_telegram(text: str, parse_mode: Optional[str] = None, timeout: int = 5) -> bool:
    """Send a Telegram message. Returns True on success, False otherwise."""
    if not telegram_enabled():
        return False
    url = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"
    payload = {"chat_id": _CHAT_ID, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code == 200:
            return True
        # log minimal error locally
        err = {"ts": int(time.time()), "status": r.status_code, "body": r.text[:200]}
        os.makedirs("data/logs", exist_ok=True)
        with open("data/logs/telegram_errors.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(err) + "\n")
        return False
    except Exception as e:
        os.makedirs("data/logs", exist_ok=True)
        with open("data/logs/telegram_errors.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": int(time.time()), "exc": str(e)}) + "\n")
        return False
